"""FASTUS Stage 4 — Coreference resolution (MVP).

Resolve pronouns and possessives to canonical character surfaces using POV,
recent-entity heuristics, and optional cast/registry hints. Produces
ResolvedMention rows only — no claims.

Relevant reading: Jurafsky — Coreference Resolution; AIMA — Knowledge-Based Agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.entity_registry import normalize_name
from app.extraction.family import CastMap
from app.nlp.entity_candidates import EntityCandidate

CorefMethod = Literal[
    "pov",
    "nearest_entity",
    "registry",
    "literal",
    "cast",
    "unresolved",
]

_POV_SUBJECT = frozenset({"i", "me", "myself"})
_POV_POSSESSIVE = frozenset({"my", "mine"})
_MALE_PRONOUN = frozenset({"he", "him", "his"})
_FEMALE_PRONOUN = frozenset({"she", "her", "hers"})
_PLURAL_PRONOUN = frozenset({"they", "them", "their", "theirs"})
_ALL_PRONOUNS = _POV_SUBJECT | _POV_POSSESSIVE | _MALE_PRONOUN | _FEMALE_PRONOUN | _PLURAL_PRONOUN

# Simple gender hints for nearest-entity matching (MVP; not exhaustive).
_FEMALE_NAME_HINTS = frozenset(
    {
        "bella",
        "isabella",
        "renée",
        "renee",
        "rosalie",
        "alice",
        "jessica",
        "angela",
        "victoria",
        "leah",
        "esme",
    }
)
_MALE_NAME_HINTS = frozenset(
    {
        "edward",
        "charlie",
        "jacob",
        "emmett",
        "jasper",
        "carlisle",
        "mike",
        "eric",
        "tyler",
        "james",
        "laurent",
        "phil",
        "billy",
    }
)

_OBJECT_FILLER_TAIL = frozenset(
    {"at", "all", "either", "anymore", "too", "yet", "still", "even", "just"}
)


@dataclass(frozen=True)
class ResolvedMention:
    mention_text: str
    resolved_surface: str
    entity_id: int | None
    confidence: float
    method: CorefMethod


@dataclass
class CorefContext:
    """Rolling mention history for pronoun resolution within a chunk."""

    pov_character: str = ""
    cast: CastMap = field(default_factory=dict)
    entity_by_norm: dict[str, EntityCandidate] = field(default_factory=dict)
    # (sentence_index, start_char, surface, entity_id, gender_hint)
    mention_history: list[tuple[int, int, str, int | None, str]] = field(
        default_factory=list
    )


def is_pronoun(surface: str) -> bool:
    head = (surface or "").strip().lower().split()[0]
    return head in _ALL_PRONOUNS


def _norm(surface: str) -> str:
    return normalize_name(surface or "")


def _gender_hint(surface: str) -> str:
    """Return male, female, plural, or unknown for a resolved character surface."""
    tokens = _norm(surface).split()
    if not tokens:
        return "unknown"
    first = tokens[0]
    if first in _FEMALE_NAME_HINTS:
        return "female"
    if first in _MALE_NAME_HINTS:
        return "male"
    if len(tokens) >= 2:
        last = tokens[-1]
        if last in _FEMALE_NAME_HINTS:
            return "female"
        if last in _MALE_NAME_HINTS:
            return "male"
    return "unknown"


def _pronoun_gender(pronoun: str) -> str:
    head = pronoun.strip().lower().split()[0]
    if head in _MALE_PRONOUN:
        return "male"
    if head in _FEMALE_PRONOUN:
        return "female"
    if head in _PLURAL_PRONOUN:
        return "plural"
    return "unknown"


def build_coref_context(
    entity_candidates: list[EntityCandidate],
    *,
    pov_character: str | None = None,
    cast: CastMap | None = None,
) -> CorefContext:
    ctx = CorefContext(
        pov_character=(pov_character or "").strip(),
        cast=dict(cast or {}),
    )
    for ec in entity_candidates:
        norm = ec.normalized_text
        prev = ctx.entity_by_norm.get(norm)
        if prev is None or ec.confidence >= prev.confidence:
            ctx.entity_by_norm[norm] = ec
    return ctx


def register_entity_mention(
    ctx: CorefContext,
    *,
    sentence_index: int,
    start_char: int,
    surface: str,
    entity_id: int | None = None,
) -> None:
    surface = (surface or "").strip()
    if not surface or is_pronoun(surface):
        return
    ctx.mention_history.append(
        (
            sentence_index,
            start_char,
            surface,
            entity_id,
            _gender_hint(surface),
        )
    )


def strip_object_filler(surface: str) -> str:
    """Drop trailing discourse particles ('him at all' -> 'him' before resolve)."""
    parts = (surface or "").strip().split()
    while len(parts) > 1 and parts[-1].lower() in _OBJECT_FILLER_TAIL:
        parts.pop()
    while len(parts) > 2 and parts[0].lower() in _OBJECT_FILLER_TAIL:
        parts.pop(0)
    return " ".join(parts)


def _entity_id_for_surface(surface: str, ctx: CorefContext) -> int | None:
    ec = ctx.entity_by_norm.get(_norm(surface))
    if ec is None:
        return None
    return ec.registry_entity_id


def _nearest_entity(
    ctx: CorefContext,
    *,
    sentence_index: int,
    mention_offset: int,
    pronoun: str,
) -> tuple[str, int | None, float] | None:
    want = _pronoun_gender(pronoun)
    window_start = max(0, sentence_index - 3)

    def _candidates(same_sentence_only: bool) -> list[tuple[int, int, str, int | None, str]]:
        out: list[tuple[int, int, str, int | None, str]] = []
        for sent_i, start, surface, eid, gender in reversed(ctx.mention_history):
            if sent_i < window_start:
                break
            if same_sentence_only and sent_i != sentence_index:
                continue
            if not same_sentence_only and sent_i > sentence_index:
                continue
            if start >= mention_offset and sent_i == sentence_index:
                continue
            out.append((sent_i, start, surface, eid, gender))
        return out

    for pool in (_candidates(True), _candidates(False)):
        for _sent_i, _start, surface, eid, gender in pool:
            if want == "plural":
                return surface, eid, 0.62
            if want == "male" and gender in ("male", "unknown"):
                return surface, eid, 0.72 if gender == "male" else 0.58
            if want == "female" and gender in ("female", "unknown"):
                return surface, eid, 0.72 if gender == "female" else 0.58
            if want == "unknown":
                return surface, eid, 0.55
    return None


def resolve_surface(
    surface: str,
    ctx: CorefContext,
    *,
    sentence_index: int = 0,
    mention_offset: int = 0,
    role: Literal["subject", "object", "possessor"] = "subject",
) -> ResolvedMention:
    """Resolve a mention surface to a canonical character/entity name."""
    raw = (surface or "").strip()
    cleaned = strip_object_filler(raw)
    head = cleaned.lower().split()[0] if cleaned else ""

    if not cleaned:
        return ResolvedMention(
            mention_text=raw,
            resolved_surface="",
            entity_id=None,
            confidence=0.0,
            method="unresolved",
        )

    pov = ctx.pov_character
    if head in _POV_SUBJECT or (role == "subject" and head == "i"):
        if pov:
            eid = _entity_id_for_surface(pov, ctx)
            return ResolvedMention(
                mention_text=raw,
                resolved_surface=pov,
                entity_id=eid,
                confidence=0.92,
                method="pov",
            )
        return ResolvedMention(
            mention_text=raw,
            resolved_surface="",
            entity_id=None,
            confidence=0.0,
            method="unresolved",
        )

    if head in _POV_POSSESSIVE or (role == "possessor" and head == "my"):
        if pov:
            eid = _entity_id_for_surface(pov, ctx)
            return ResolvedMention(
                mention_text=raw,
                resolved_surface=pov,
                entity_id=eid,
                confidence=0.9,
                method="pov",
            )
        return ResolvedMention(
            mention_text=raw,
            resolved_surface="",
            entity_id=None,
            confidence=0.0,
            method="unresolved",
        )

    if head in _ALL_PRONOUNS:
        nearest = _nearest_entity(
            ctx,
            sentence_index=sentence_index,
            mention_offset=mention_offset,
            pronoun=head,
        )
        if nearest:
            surface_res, eid, conf = nearest
            return ResolvedMention(
                mention_text=raw,
                resolved_surface=surface_res,
                entity_id=eid,
                confidence=conf,
                method="nearest_entity",
            )
        return ResolvedMention(
            mention_text=raw,
            resolved_surface="",
            entity_id=None,
            confidence=0.0,
            method="unresolved",
        )

    # Cast shortcuts for family role names (dad, mom).
    cast_key = head.rstrip(".,;:!?")
    if cast_key in ctx.cast:
        name = ctx.cast[cast_key]
        return ResolvedMention(
            mention_text=raw,
            resolved_surface=name,
            entity_id=_entity_id_for_surface(name, ctx),
            confidence=0.75,
            method="cast",
        )

    # Registry / literal proper noun.
    ec = ctx.entity_by_norm.get(_norm(cleaned))
    if ec is not None:
        method: CorefMethod = "registry" if ec.registry_entity_id else "literal"
        conf = ec.confidence if method == "registry" else 0.85
        return ResolvedMention(
            mention_text=raw,
            resolved_surface=ec.surface_text,
            entity_id=ec.registry_entity_id,
            confidence=conf,
            method=method,
        )

    if re.match(r"^[A-Z]", cleaned):
        return ResolvedMention(
            mention_text=raw,
            resolved_surface=cleaned,
            entity_id=None,
            confidence=0.8,
            method="literal",
        )

    return ResolvedMention(
        mention_text=raw,
        resolved_surface=cleaned,
        entity_id=None,
        confidence=0.5,
        method="literal",
    )


def seed_context_from_sentence_entities(
    ctx: CorefContext,
    entity_candidates: list[EntityCandidate],
    sentence_index: int,
) -> None:
    """Register entity candidates that appear in a sentence before resolving pronouns."""
    for ec in entity_candidates:
        if ec.sentence_index != sentence_index:
            continue
        if ec.entity_type_guess not in ("character", "group"):
            continue
        register_entity_mention(
            ctx,
            sentence_index=sentence_index,
            start_char=ec.start_char,
            surface=ec.surface_text,
            entity_id=ec.registry_entity_id,
        )
