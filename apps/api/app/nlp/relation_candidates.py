"""FASTUS Stage 4 — Complex phrases / dependency relation candidates.

Build subject–predicate–object relation candidates from dependency parses,
family identity patterns, and emotional state phrases. Applies coreference and
fragment rejection; produces RelationCandidate rows only — no claims.

Relevant reading: Jurafsky — Dependency Parsing; AIMA — First-Order Logic (negation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.extraction.family import CastMap, discover_cast_from_text
from app.extraction.structural import _predicate_from_verb
from app.nlp.chapter_parse import ParsedChunk, ParsedSentence, ParsedToken
from app.nlp.coreference import (
    CorefContext,
    build_coref_context,
    resolve_surface,
    seed_context_from_sentence_entities,
    strip_object_filler,
)
from app.nlp.entity_candidates import EntityCandidate
from app.nlp.negation import has_identity_negation
from app.nlp.phrase_candidates import (
    PhraseCandidate,
    _ALL_FAMILY_RELATIONS,
    _EMOTION_ADJECTIVES,
    _EMOTION_LEMMAS,
    _FAMILY_RE,
)

RelationOrigin = Literal["dependency", "family_rule", "state_rule", "pattern"]

_RESOLVED_COREF_METHODS = frozenset(
    {"literal", "registry", "pov", "nearest_entity", "cast"}
)

_AUXILIARY_SUBJECT_STARTS = re.compile(
    r"^(?:did|does|do|was|were|had|have|has|is|are|am|will|would|could|should|can|not|never)\b",
    re.I,
)

_FAMILY_TO_PREDICATE: dict[str, str] = {
    "father": "father_of",
    "dad": "father_of",
    "pa": "father_of",
    "papa": "father_of",
    "daddy": "father_of",
    "mother": "mother_of",
    "mom": "mother_of",
    "mum": "mother_of",
    "mama": "mother_of",
    "mommy": "mother_of",
    "mammy": "mother_of",
    "parent": "parent_of",
    "parents": "parent_of",
    "son": "son_of",
    "daughter": "daughter_of",
    "child": "child_of",
    "children": "child_of",
    "brother": "brother_of",
    "sister": "sister_of",
    "sibling": "sibling_of",
    "grandfather": "grandfather_of",
    "grandmother": "grandmother_of",
    "grandpa": "grandfather_of",
    "grandma": "grandmother_of",
    "husband": "husband_of",
    "wife": "wife_of",
    "spouse": "spouse_of",
    "stepfather": "stepfather_of",
    "stepmother": "stepmother_of",
    "stepdad": "stepfather_of",
    "stepmom": "stepmother_of",
    "uncle": "uncle_of",
    "aunt": "aunt_of",
    "cousin": "cousin_of",
    "nephew": "nephew_of",
    "niece": "niece_of",
    "father-in-law": "father_in_law_of",
    "mother-in-law": "mother_in_law_of",
    "brother-in-law": "brother_in_law_of",
    "sister-in-law": "sister_in_law_of",
    "guardian": "guardian_of",
    "ward": "ward_of",
}

_FAMILY_IDENTITY_NEGATED_RE = re.compile(
    rf"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+was\s+(?:not|never)\s+my\s+"
    rf"({'|'.join(re.escape(t) for t in sorted(_ALL_FAMILY_RELATIONS, key=len, reverse=True))})\b",
    re.I,
)
_FAMILY_IDENTITY_POSITIVE_RE = re.compile(
    rf"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+was\s+my\s+"
    rf"({'|'.join(re.escape(t) for t in sorted(_ALL_FAMILY_RELATIONS, key=len, reverse=True))})\b",
    re.I,
)
_VERB_RELATION_FALLBACK_RE = re.compile(
    r"\b(?:I|([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\s+"
    r"(?:did|do|does|had|have|has|was|were|is|are|am)?\s*"
    r"(?:not|never)?\s*"
    r"(trust|trusted|love|loved|hate|hated|fear|feared|miss|missed|distrust|distrusted)\s+"
    r"(\w+(?:\s+\w+)?)",
    re.I,
)
_STATE_RELATION_FALLBACK_RE = re.compile(
    r"\b(?:I|([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\s+was\s+(?:not|never)?\s*"
    r"(uncomfortable|jealous|angry|afraid|suspicious|curious|happy|sad)\s+"
    r"(?:with|of|about)\s+([A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+)?)",
    re.I,
)


@dataclass(frozen=True)
class RelationCandidate:
    subject_surface: str
    subject_entity_id: int | None
    predicate_raw: str
    predicate_normalized: str
    object_surface: str
    object_entity_id: int | None
    polarity: bool
    confidence: float
    evidence_text: str
    start_char: int
    end_char: int
    sentence_index: int
    chunk_index: int
    extraction_origin: RelationOrigin


def _children_of(head_idx: int, tokens: list[ParsedToken]) -> list[int]:
    return [i for i, t in enumerate(tokens) if t.head == head_idx]


def _span_text(tokens: list[ParsedToken], indices: list[int]) -> str:
    return " ".join(tokens[i].text for i in sorted(indices)).strip()


def _subtree_indices(root_idx: int, tokens: list[ParsedToken], *, max_depth: int = 8) -> list[int]:
    """Collect token indices under root (bounded; guards parser cycles)."""
    indices: list[int] = []
    stack: list[tuple[int, int]] = [(root_idx, 0)]
    seen: set[int] = set()
    while stack:
        idx, depth = stack.pop()
        if idx in seen or depth > max_depth or idx < 0 or idx >= len(tokens):
            continue
        seen.add(idx)
        indices.append(idx)
        for child in _children_of(idx, tokens):
            stack.append((child, depth + 1))
    return sorted(indices)


def _negated_subtree(tokens: list[ParsedToken], root_idx: int, sentence_text: str) -> bool:
    indices = _subtree_indices(root_idx, tokens)
    if any(tokens[i].is_negation for i in indices):
        return True
    return has_identity_negation(sentence_text)


def _family_predicate(relation: str) -> str:
    key = " ".join((relation or "").strip().lower().split())
    return _FAMILY_TO_PREDICATE.get(key, f"{key.replace('-', '_')}_of")


def _confidence_for_resolved_pair(
    *,
    subject_method: str,
    object_method: str,
    has_object: bool,
    base: float,
) -> float:
    """Slight boost when both ends resolved (final auto-approve may happen at extract)."""
    if (
        has_object
        and subject_method in _RESOLVED_COREF_METHODS
        and object_method in _RESOLVED_COREF_METHODS
    ):
        return max(base, 0.88)
    return base


def reject_reason_for_relation(
    *,
    subject_surface: str,
    object_surface: str,
    predicate_normalized: str,
    subject_method: str = "literal",
    object_method: str = "literal",
) -> str | None:
    subj = " ".join((subject_surface or "").strip().lower().split())
    obj = " ".join((object_surface or "").strip().lower().split())

    if not subj:
        return "missing subject"

    if _AUXILIARY_SUBJECT_STARTS.match(subj):
        return "auxiliary/fragment subject"

    if subject_method == "unresolved":
        return "unresolved pronoun subject"

    if object_method == "unresolved":
        return "unresolved pronoun object"

    if not obj and predicate_normalized not in (
        "father_of",
        "mother_of",
        "parent_of",
    ):
        return "missing object"

    obj_head = obj.split()[0] if obj else ""
    if obj_head in {"him", "her", "them", "me", "you", "it"}:
        return "unresolved pronoun object"

    if len(obj.split()) > 1 and obj.split()[-1] in ("all", "either", "anymore"):
        return "junk object fragment"

    if subj == obj and predicate_normalized.endswith("_of"):
        return "self-referential family relation"

    return None


def _emit_relation(
    *,
    subject: str,
    subject_id: int | None,
    predicate_raw: str,
    predicate_normalized: str,
    obj: str,
    object_id: int | None,
    polarity: bool,
    confidence: float,
    evidence: str,
    start: int,
    end: int,
    sentence_index: int,
    chunk_index: int,
    origin: RelationOrigin,
    subject_method: str = "literal",
    object_method: str = "literal",
    seen: set[tuple[str, str, str, bool]],
    out: list[RelationCandidate],
) -> None:
    reason = reject_reason_for_relation(
        subject_surface=subject,
        object_surface=obj,
        predicate_normalized=predicate_normalized,
        subject_method=subject_method,
        object_method=object_method,
    )
    if reason:
        return

    key = (
        subject.strip().lower(),
        predicate_normalized.strip().lower(),
        obj.strip().lower(),
        polarity,
    )
    if key in seen:
        return
    seen.add(key)

    out.append(
        RelationCandidate(
            subject_surface=subject,
            subject_entity_id=subject_id,
            predicate_raw=predicate_raw,
            predicate_normalized=predicate_normalized,
            object_surface=obj,
            object_entity_id=object_id,
            polarity=polarity,
            confidence=confidence,
            evidence_text=evidence[:500],
            start_char=start,
            end_char=end,
            sentence_index=sentence_index,
            chunk_index=chunk_index,
            extraction_origin=origin,
        )
    )


def _resolve_role(
    surface: str,
    ctx: CorefContext,
    *,
    sentence_index: int,
    mention_offset: int,
    role: Literal["subject", "object", "possessor"],
):
    res = resolve_surface(
        surface,
        ctx,
        sentence_index=sentence_index,
        mention_offset=mention_offset,
        role=role,
    )
    return res.resolved_surface, res.entity_id, res.method


def _family_identity_from_sentence(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    ctx: CorefContext,
    *,
    seen: set[tuple[str, str, str, bool]],
    out: list[RelationCandidate],
) -> None:
    sent_idx = _sentence_index(parsed, sent.start_char)
    pov = ctx.pov_character
    if not pov:
        return

    if parsed.has_dependencies:
        for idx in range(sent.token_start, sent.token_end):
            tok = tokens[idx]
            if tok.dep != "ROOT" or tok.lemma.lower() != "be":
                continue
            subj_surface = ""
            subj_offset = sent.start_char
            family_relation = ""
            for child in _children_of(idx, tokens):
                ct = tokens[child]
                if ct.dep in ("nsubj", "nsubjpass") and not subj_surface:
                    subj_indices = _subtree_indices(child, tokens)
                    subj_surface = _span_text(tokens, subj_indices)
                    subj_offset = tokens[child].start_char
                if ct.dep in ("attr", "acomp"):
                    attr_text = _span_text(tokens, _subtree_indices(child, tokens))
                    fm = _FAMILY_RE.search(attr_text)
                    if fm:
                        family_relation = fm.group(1).lower()

            if not subj_surface or not family_relation:
                continue

            subj, subj_id, subj_method = _resolve_role(
                subj_surface,
                ctx,
                sentence_index=sent_idx,
                mention_offset=subj_offset,
                role="subject",
            )
            polarity = not _negated_subtree(tokens, idx, sent.text)
            pred = _family_predicate(family_relation)
            evidence = parsed.text[sent.start_char : sent.end_char].strip()
            _emit_relation(
                subject=subj,
                subject_id=subj_id,
                predicate_raw=family_relation,
                predicate_normalized=pred,
                obj=pov,
                object_id=_entity_id_for(ctx, pov),
                polarity=polarity,
                confidence=0.82,
                evidence=evidence,
                start=sent.start_char,
                end=sent.end_char,
                sentence_index=sent_idx,
                chunk_index=parsed.chunk_index,
                origin="dependency",
                subject_method=subj_method,
                object_method="pov",
                seen=seen,
                out=out,
            )
        return

    for regex, default_polarity in (
        (_FAMILY_IDENTITY_NEGATED_RE, False),
        (_FAMILY_IDENTITY_POSITIVE_RE, True),
    ):
        for m in regex.finditer(sent.text):
            parent = m.group(1).strip()
            relation = m.group(2).lower()
            polarity = default_polarity
            if has_identity_negation(m.group(0)):
                polarity = False
            abs_start = sent.start_char + m.start()
            subj, subj_id, subj_method = _resolve_role(
                parent,
                ctx,
                sentence_index=sent_idx,
                mention_offset=abs_start,
                role="subject",
            )
            pred = _family_predicate(relation)
            _emit_relation(
                subject=subj,
                subject_id=subj_id,
                predicate_raw=relation,
                predicate_normalized=pred,
                obj=pov,
                object_id=_entity_id_for(ctx, pov),
                polarity=polarity,
                confidence=0.78,
                evidence=m.group(0),
                start=abs_start,
                end=sent.start_char + m.end(),
                sentence_index=sent_idx,
                chunk_index=parsed.chunk_index,
                origin="family_rule",
                subject_method=subj_method,
                object_method="pov",
                seen=seen,
                out=out,
            )


def _entity_id_for(ctx: CorefContext, surface: str) -> int | None:
    res = resolve_surface(surface, ctx, role="object")
    return res.entity_id


def _svo_from_sentence(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    ctx: CorefContext,
    *,
    seen: set[tuple[str, str, str, bool]],
    out: list[RelationCandidate],
) -> None:
    sent_idx = _sentence_index(parsed, sent.start_char)

    if parsed.has_dependencies:
        for idx in range(sent.token_start, sent.token_end):
            tok = tokens[idx]
            if tok.dep != "ROOT" or tok.pos != "VERB":
                continue
            if tok.lemma.lower() not in _EMOTION_LEMMAS:
                continue

            subj_surface = ""
            subj_offset = sent.start_char
            obj_surface = ""
            obj_offset = sent.start_char

            for child in _children_of(idx, tokens):
                ct = tokens[child]
                if ct.dep in ("nsubj", "nsubjpass", "csubj") and not subj_surface:
                    subj_surface = _span_text(tokens, _subtree_indices(child, tokens))
                    subj_offset = ct.start_char
                elif ct.dep in ("dobj", "attr", "oprd") and not obj_surface:
                    obj_surface = _span_text(tokens, _subtree_indices(child, tokens))
                    obj_offset = ct.start_char
                elif ct.dep == "prep" and not obj_surface:
                    for gc in _children_of(child, tokens):
                        if tokens[gc].dep == "pobj":
                            obj_surface = _span_text(tokens, _subtree_indices(gc, tokens))
                            obj_offset = tokens[gc].start_char

            if not subj_surface:
                continue
            obj_surface = strip_object_filler(obj_surface)

            subj, subj_id, subj_method = _resolve_role(
                subj_surface,
                ctx,
                sentence_index=sent_idx,
                mention_offset=subj_offset,
                role="subject",
            )
            obj, obj_id, obj_method = _resolve_role(
                obj_surface,
                ctx,
                sentence_index=sent_idx,
                mention_offset=obj_offset,
                role="object",
            )
            polarity = not _negated_subtree(tokens, idx, sent.text)
            pred_norm = _predicate_from_verb(tok.lemma or tok.text)
            evidence = parsed.text[sent.start_char : sent.end_char].strip()
            conf = _confidence_for_resolved_pair(
                subject_method=subj_method,
                object_method=obj_method,
                has_object=bool(obj),
                base=0.8,
            )
            _emit_relation(
                subject=subj,
                subject_id=subj_id,
                predicate_raw=tok.lemma or tok.text,
                predicate_normalized=pred_norm,
                obj=obj,
                object_id=obj_id,
                polarity=polarity,
                confidence=conf,
                evidence=evidence,
                start=sent.start_char,
                end=sent.end_char,
                sentence_index=sent_idx,
                chunk_index=parsed.chunk_index,
                origin="dependency",
                subject_method=subj_method,
                object_method=obj_method,
                seen=seen,
                out=out,
            )
        return

    for m in _VERB_RELATION_FALLBACK_RE.finditer(sent.text):
        subj_raw = (m.group(1) or "I").strip()
        verb = m.group(2).lower()
        obj_raw = strip_object_filler(m.group(3))
        abs_start = sent.start_char + m.start()
        subj, subj_id, subj_method = _resolve_role(
            subj_raw,
            ctx,
            sentence_index=sent_idx,
            mention_offset=abs_start,
            role="subject",
        )
        obj, obj_id, obj_method = _resolve_role(
            obj_raw,
            ctx,
            sentence_index=sent_idx,
            mention_offset=abs_start + m.start(3),
            role="object",
        )
        polarity = not bool(re.search(r"\b(?:not|never)\b", m.group(0), re.I))
        pred_norm = _predicate_from_verb(verb)
        conf = _confidence_for_resolved_pair(
            subject_method=subj_method,
            object_method=obj_method,
            has_object=bool(obj),
            base=0.72,
        )
        _emit_relation(
            subject=subj,
            subject_id=subj_id,
            predicate_raw=verb,
            predicate_normalized=pred_norm,
            obj=obj,
            object_id=obj_id,
            polarity=polarity,
            confidence=conf,
            evidence=m.group(0),
            start=abs_start,
            end=sent.start_char + m.end(),
            sentence_index=sent_idx,
            chunk_index=parsed.chunk_index,
            origin="pattern",
            subject_method=subj_method,
            object_method=obj_method,
            seen=seen,
            out=out,
        )


def _state_from_sentence(
    parsed: ParsedChunk,
    sent: ParsedSentence,
    tokens: list[ParsedToken],
    ctx: CorefContext,
    *,
    seen: set[tuple[str, str, str, bool]],
    out: list[RelationCandidate],
) -> None:
    sent_idx = _sentence_index(parsed, sent.start_char)

    if parsed.has_dependencies:
        for idx in range(sent.token_start, sent.token_end):
            tok = tokens[idx]
            if tok.dep != "ROOT" or tok.lemma.lower() != "be":
                continue

            adj_idx: int | None = None
            for child in _children_of(idx, tokens):
                ct = tokens[child]
                if ct.dep in ("acomp", "attr"):
                    if ct.lemma.lower() in _EMOTION_ADJECTIVES or ct.text.lower() in _EMOTION_ADJECTIVES:
                        adj_idx = child
                        break
            if adj_idx is None:
                continue

            subj_surface = ""
            subj_offset = sent.start_char
            obj_surface = ""
            obj_offset = sent.start_char

            for child in _children_of(idx, tokens):
                ct = tokens[child]
                if ct.dep in ("nsubj", "nsubjpass") and not subj_surface:
                    subj_surface = _span_text(tokens, _subtree_indices(child, tokens))
                    subj_offset = ct.start_char

            for child in _children_of(adj_idx, tokens):
                if tokens[child].dep == "prep":
                    for gc in _children_of(child, tokens):
                        if tokens[gc].dep == "pobj":
                            obj_surface = _span_text(tokens, _subtree_indices(gc, tokens))
                            obj_offset = tokens[gc].start_char

            subj, subj_id, subj_method = _resolve_role(
                subj_surface,
                ctx,
                sentence_index=sent_idx,
                mention_offset=subj_offset,
                role="subject",
            )
            obj, obj_id, obj_method = _resolve_role(
                obj_surface,
                ctx,
                sentence_index=sent_idx,
                mention_offset=obj_offset,
                role="object",
            )
            adj_tok = tokens[adj_idx]
            polarity = not _negated_subtree(tokens, idx, sent.text)
            pred = adj_tok.lemma.lower() or adj_tok.text.lower()
            evidence = parsed.text[sent.start_char : sent.end_char].strip()
            _emit_relation(
                subject=subj,
                subject_id=subj_id,
                predicate_raw=pred,
                predicate_normalized=pred,
                obj=obj,
                object_id=obj_id,
                polarity=polarity,
                confidence=0.76,
                evidence=evidence,
                start=sent.start_char,
                end=sent.end_char,
                sentence_index=sent_idx,
                chunk_index=parsed.chunk_index,
                origin="state_rule",
                subject_method=subj_method,
                object_method=obj_method,
                seen=seen,
                out=out,
            )
        return

    for m in _STATE_RELATION_FALLBACK_RE.finditer(sent.text):
        subj_raw = (m.group(1) or "I").strip()
        adj = m.group(2).lower()
        obj_raw = m.group(3).strip()
        abs_start = sent.start_char + m.start()
        subj, subj_id, subj_method = _resolve_role(
            subj_raw,
            ctx,
            sentence_index=sent_idx,
            mention_offset=abs_start,
            role="subject",
        )
        obj, obj_id, obj_method = _resolve_role(
            obj_raw,
            ctx,
            sentence_index=sent_idx,
            mention_offset=abs_start,
            role="object",
        )
        polarity = not bool(re.search(r"\b(?:not|never)\b", m.group(0), re.I))
        _emit_relation(
            subject=subj,
            subject_id=subj_id,
            predicate_raw=adj,
            predicate_normalized=adj,
            obj=obj,
            object_id=obj_id,
            polarity=polarity,
            confidence=0.7,
            evidence=m.group(0),
            start=abs_start,
            end=sent.start_char + m.end(),
            sentence_index=sent_idx,
            chunk_index=parsed.chunk_index,
            origin="state_rule",
            subject_method=subj_method,
            object_method=obj_method,
            seen=seen,
            out=out,
        )


def _sentence_index(parsed: ParsedChunk, offset: int) -> int:
    for i, sent in enumerate(parsed.sentences):
        if sent.start_char <= offset < sent.end_char:
            return i
    return 0


def extract_relation_candidates(
    parsed: ParsedChunk,
    entity_candidates: list[EntityCandidate],
    phrase_candidates: list[PhraseCandidate] | None = None,
    *,
    pov_character: str | None = None,
    cast: CastMap | None = None,
) -> list[RelationCandidate]:
    """
    Build relation candidates from parsed text with coreference resolution.

    Processes sentences in order so pronouns can resolve to recent entities.
    phrase_candidates is accepted for API symmetry (Stage 5 may cross-reference).
    """
    del phrase_candidates  # reserved for Stage 5 semantic patterns

    cast_map = cast if cast is not None else discover_cast_from_text(parsed.text)
    ctx = build_coref_context(
        entity_candidates,
        pov_character=pov_character,
        cast=cast_map,
    )

    seen: set[tuple[str, str, str, bool]] = set()
    out: list[RelationCandidate] = []
    tokens = parsed.tokens

    for sent in parsed.sentences:
        sent_idx = _sentence_index(parsed, sent.start_char)
        seed_context_from_sentence_entities(ctx, entity_candidates, sent_idx)
        _family_identity_from_sentence(parsed, sent, tokens, ctx, seen=seen, out=out)
        _svo_from_sentence(parsed, sent, tokens, ctx, seen=seen, out=out)
        _state_from_sentence(parsed, sent, tokens, ctx, seen=seen, out=out)

    return sorted(out, key=lambda r: (r.start_char, r.end_char))


def extract_relation_candidates_from_text(
    text: str,
    chunk_index: int = 0,
    *,
    pov_character: str | None = None,
    cast: CastMap | None = None,
) -> list[RelationCandidate]:
    from app.nlp.chapter_parse import parse_chunk
    from app.nlp.entity_candidates import extract_entity_candidates
    from app.nlp.phrase_candidates import extract_phrase_candidates

    parsed = parse_chunk(text, chunk_index)
    entities = extract_entity_candidates(parsed, pov_character=pov_character)
    phrases = extract_phrase_candidates(parsed, pov_character=pov_character)
    return extract_relation_candidates(
        parsed,
        entities,
        phrases,
        pov_character=pov_character,
        cast=cast,
    )
