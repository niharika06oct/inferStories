"""FASTUS Stage 2 - Complex Words / NER.

Extract entity *candidates* from a parsed chunk: spaCy NER spans, proper-noun
sequences, and story-registry alias hits. Produces EntityCandidate rows only —
no claims.

Relevant reading: Jurafsky - Named Entity Recognition; DDIA Ch. 2 entity normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.entity_classification import EntityType, classify_entity_surface
from app.entity_registry import find_entity_by_name, is_placeholder_entity_name, normalize_name
from app.nlp.chapter_parse import ParsedChunk, ParsedSentence, ParsedToken, parse_chunk

EntityCandidateSource = Literal["spacy", "registry", "rule"]

# spaCy entity labels -> InferStories entity types (hard rules from FASTUS plan).
_SPACY_TYPE_MAP: dict[str, tuple[EntityType, float]] = {
    "PERSON": ("character", 0.92),
    "GPE": ("place", 0.9),
    "LOC": ("place", 0.88),
    "FAC": ("place", 0.85),
    "ORG": ("group", 0.85),
    "NORP": ("group", 0.82),
    "PRODUCT": ("object", 0.8),
    "WORK_OF_ART": ("object", 0.78),
    "EVENT": ("concept", 0.75),
}

# Single-token surfaces that are never entity anchors.
_SKIP_SURFACES = frozenset(
    {
        "i",
        "me",
        "my",
        "myself",
        "he",
        "she",
        "they",
        "him",
        "her",
        "them",
        "it",
        "we",
        "us",
        "you",
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "of",
        "for",
    }
)

_PROPN_SEQUENCE_RE = re.compile(
    r"\b[A-Z][a-z]+(?:\s+(?:van|de|von|al)\s+[A-Z][a-z]+|\s+[A-Z][a-z]+)*\b"
)


@dataclass(frozen=True)
class EntityCandidate:
    surface_text: str
    normalized_text: str
    entity_type_guess: EntityType
    confidence: float
    start_char: int
    end_char: int
    source: EntityCandidateSource
    sentence_index: int
    chunk_index: int
    registry_entity_id: int | None = None
    spacy_label: str = ""


@dataclass(frozen=True)
class _RawSpan:
    surface: str
    start: int
    end: int
    source: EntityCandidateSource
    spacy_label: str
    type_guess: EntityType
    confidence: float


def _sentence_index(parsed: ParsedChunk, offset: int) -> int:
    for i, sent in enumerate(parsed.sentences):
        if sent.start_char <= offset < sent.end_char:
            return i
    return 0


def _sentence_text(parsed: ParsedChunk, index: int) -> str:
    if 0 <= index < len(parsed.sentences):
        return parsed.sentences[index].text
    return parsed.text


def _type_from_spacy_label(label: str) -> tuple[EntityType, float]:
    return _SPACY_TYPE_MAP.get(label, ("character", 0.55))


def _flush_ner_group(
    tokens: list[ParsedToken],
    start_idx: int,
    end_idx: int,
    label: str,
    out: list[_RawSpan],
) -> None:
    if start_idx >= end_idx or not label:
        return
    surface = " ".join(t.text for t in tokens[start_idx:end_idx]).strip()
    if not surface or normalize_name(surface) in _SKIP_SURFACES:
        return
    etype, conf = _type_from_spacy_label(label)
    out.append(
        _RawSpan(
            surface=surface,
            start=tokens[start_idx].start_char,
            end=tokens[end_idx - 1].end_char,
            source="spacy",
            spacy_label=label,
            type_guess=etype,
            confidence=conf,
        )
    )


def _spacy_ner_spans(tokens: list[ParsedToken]) -> list[_RawSpan]:
    """Group consecutive tokens sharing the same spaCy ent_type."""
    spans: list[_RawSpan] = []
    i = 0
    while i < len(tokens):
        label = tokens[i].ent_type
        if not label:
            i += 1
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].ent_type == label:
            j += 1
        _flush_ner_group(tokens, i, j, label, spans)
        i = j
    return spans


def _propn_spans(tokens: list[ParsedToken], covered: list[tuple[int, int]]) -> list[_RawSpan]:
    """Proper-noun token runs not already covered by NER spans."""
    spans: list[_RawSpan] = []
    i = 0
    while i < len(tokens):
        if tokens[i].pos != "PROPN":
            i += 1
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].pos == "PROPN":
            j += 1
        start, end = tokens[i].start_char, tokens[j - 1].end_char
        if any(not (end <= cs or start >= ce) for cs, ce in covered):
            i = j
            continue
        surface = " ".join(t.text for t in tokens[i:j]).strip()
        if surface and normalize_name(surface) not in _SKIP_SURFACES:
            spans.append(
                _RawSpan(
                    surface=surface,
                    start=start,
                    end=end,
                    source="rule",
                    spacy_label="",
                    type_guess="character",
                    confidence=0.72,
                )
            )
        i = j
    return spans


def _regex_propn_spans(text: str, covered: list[tuple[int, int]]) -> list[_RawSpan]:
    """Capitalized name regex for fallback tokenization (no POS/NER)."""
    spans: list[_RawSpan] = []
    for m in _PROPN_SEQUENCE_RE.finditer(text):
        start, end = m.start(), m.end()
        if any(not (end <= cs or start >= ce) for cs, ce in covered):
            continue
        surface = m.group(0).strip()
        if normalize_name(surface) in _SKIP_SURFACES:
            continue
        spans.append(
            _RawSpan(
                surface=surface,
                start=start,
                end=end,
                source="rule",
                spacy_label="",
                type_guess="character",
                confidence=0.65,
            )
        )
    return spans


def _refine_type(
    span: _RawSpan,
    *,
    sentence: str,
) -> tuple[EntityType, float]:
    if span.source == "spacy" and span.spacy_label:
        return span.type_guess, span.confidence
    etype, conf = classify_entity_surface(
        span.surface,
        sentence=sentence,
        evidence=span.surface,
        role="subject",
    )
    return etype, conf


def _attach_registry(
    span: _RawSpan,
    *,
    db: Session | None,
    story_id: int | None,
    sentence: str,
) -> EntityCandidate:
    etype, conf = _refine_type(span, sentence=sentence)
    source: EntityCandidateSource = span.source
    registry_id: int | None = None

    if db is not None and story_id is not None:
        row = find_entity_by_name(db, story_id, span.surface)
        if row is not None:
            registry_id = row.id
            source = "registry"
            etype = row.entity_type  # type: ignore[assignment]
            conf = max(conf, row.type_confidence or 0.85)

    return EntityCandidate(
        surface_text=span.surface,
        normalized_text=normalize_name(span.surface),
        entity_type_guess=etype,
        confidence=conf,
        start_char=span.start,
        end_char=span.end,
        source=source,
        sentence_index=0,  # filled by caller
        chunk_index=0,
        registry_entity_id=registry_id,
        spacy_label=span.spacy_label,
    )


def _dedupe_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    """Drop exact duplicate spans; prefer registry > spacy > rule at same offset."""
    source_rank = {"registry": 3, "spacy": 2, "rule": 1}
    by_key: dict[tuple[int, int, str], EntityCandidate] = {}
    for c in candidates:
        key = (c.start_char, c.end_char, c.normalized_text)
        prev = by_key.get(key)
        if prev is None or source_rank.get(c.source, 0) > source_rank.get(prev.source, 0):
            by_key[key] = c
    return sorted(by_key.values(), key=lambda c: (c.start_char, c.end_char))


def extract_entity_candidates(
    parsed: ParsedChunk,
    *,
    db: Session | None = None,
    story_id: int | None = None,
    pov_character: str | None = None,
) -> list[EntityCandidate]:
    """
    Build entity candidates from a ParsedChunk.

    Optional db/story_id resolve surfaces against the story entity registry.
    pov_character is reserved for Stage 4 coreference; placeholder surfaces are
    skipped here.
    """
    del pov_character  # Stage 4 will wire first-person → POV resolution.

    raw: list[_RawSpan] = []
    if parsed.tokens:
        raw.extend(_spacy_ner_spans(parsed.tokens))
        covered = [(s.start, s.end) for s in raw]
        raw.extend(_propn_spans(parsed.tokens, covered))
    else:
        raw.extend(_regex_propn_spans(parsed.text, []))

    candidates: list[EntityCandidate] = []
    for span in raw:
        if is_placeholder_entity_name(span.surface):
            continue
        sent_idx = _sentence_index(parsed, span.start)
        sentence = _sentence_text(parsed, sent_idx)
        cand = _attach_registry(
            span,
            db=db,
            story_id=story_id,
            sentence=sentence,
        )
        candidates.append(
            EntityCandidate(
                surface_text=cand.surface_text,
                normalized_text=cand.normalized_text,
                entity_type_guess=cand.entity_type_guess,
                confidence=cand.confidence,
                start_char=cand.start_char,
                end_char=cand.end_char,
                source=cand.source,
                sentence_index=sent_idx,
                chunk_index=parsed.chunk_index,
                registry_entity_id=cand.registry_entity_id,
                spacy_label=cand.spacy_label,
            )
        )

    return _dedupe_candidates(candidates)


def extract_entity_candidates_from_text(
    text: str,
    chunk_index: int = 0,
    *,
    db: Session | None = None,
    story_id: int | None = None,
    pov_character: str | None = None,
) -> list[EntityCandidate]:
    """Parse a text chunk then extract entity candidates."""
    parsed = parse_chunk(text, chunk_index)
    return extract_entity_candidates(
        parsed,
        db=db,
        story_id=story_id,
        pov_character=pov_character,
    )
