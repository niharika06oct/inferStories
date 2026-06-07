"""FASTUS Stage 5 — Semantic patterns.

Map Stage 4 RelationCandidates to ClaimDrafts: claim_type by entity types,
predicate normalization, polarity-aware claim text, and review status.

Relevant reading: Jurafsky — Information Extraction, Relation Extraction;
AIMA — Knowledge Representation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.entity_classification import EntityType, classify_entity_surface
from app.entity_registry import normalize_name
from app.extraction.schema import CLAIM_TYPES, CanonLevel, ExtractedClaim
from app.extraction.structural import _predicate_from_verb
from app.nlp.entity_candidates import EntityCandidate
from app.nlp.phrase_candidates import _EMOTION_ADJECTIVES
from app.nlp.relation_candidates import RelationCandidate

ClaimDraftStatus = Literal["suggested", "needs_review", "approved"]
FastusOrigin = Literal["fastus"]

CONFIDENCE_AUTO_APPROVE = 0.90
CONFIDENCE_NEEDS_REVIEW = 0.65

_FAMILY_PREDICATE_SUFFIX = "_of"
_LOCATION_PREDICATES = frozenset(
    {"in", "at", "from", "to", "near", "around", "lives_in", "located_in", "traveled_to"}
)
_TIME_MARKER_RE = re.compile(
    r"\b(?:yesterday|today|tomorrow|last\s+(?:night|week|month|year|summer|winter)|"
    r"next\s+(?:day|week|month|year)|before|after|when|then|always|years?\s+ago)\b",
    re.I,
)

_CHARACTER_TYPES = frozenset({"character", "animal", "group"})
_PLACE_TYPES = frozenset({"place"})
_OBJECT_TYPES = frozenset({"object", "concept"})


@dataclass(frozen=True)
class ClaimDraft:
    subject: str
    subject_entity_id: int | None
    predicate: str
    target: str
    object_entity_id: int | None
    claim_type: str
    claim: str
    polarity: bool
    confidence: float
    evidence_text: str
    start_char: int
    end_char: int
    chunk_index: int
    status: ClaimDraftStatus
    generation_origin: FastusOrigin = "fastus"
    canon_level: CanonLevel = "active"


def status_for_confidence(confidence: float) -> ClaimDraftStatus:
    if confidence >= CONFIDENCE_AUTO_APPROVE:
        return "approved"
    if confidence >= CONFIDENCE_NEEDS_REVIEW:
        return "needs_review"
    return "suggested"


def normalize_predicate(raw: str) -> str:
    """Normalize verb/adjective surface to canonical predicate slug."""
    key = (raw or "").strip().lower()
    if not key:
        return ""
    if key.endswith(_FAMILY_PREDICATE_SUFFIX):
        return key.replace(" ", "_")
    if key in _EMOTION_ADJECTIVES:
        return key
    return _predicate_from_verb(key)


def _entity_type_for_surface(
    surface: str,
    entity_candidates: list[EntityCandidate],
    *,
    evidence: str,
) -> EntityType:
    norm = normalize_name(surface)
    best: EntityCandidate | None = None
    for ec in entity_candidates:
        if ec.normalized_text == norm:
            if best is None or ec.confidence >= best.confidence:
                best = ec
    if best is not None:
        return best.entity_type_guess
    etype, _ = classify_entity_surface(
        surface,
        sentence=evidence,
        evidence=surface,
        role="subject",
    )
    return etype


def infer_claim_type(
    *,
    subject_type: EntityType,
    object_type: EntityType,
    predicate: str,
    evidence_text: str,
) -> str:
    pred = (predicate or "").strip().lower()

    if pred.endswith(_FAMILY_PREDICATE_SUFFIX):
        return "relationship_state"

    if pred in _LOCATION_PREDICATES or pred.endswith("_in") or pred.endswith("_at"):
        return "place_preference"

    if _TIME_MARKER_RE.search(evidence_text or ""):
        return "timeline_fact"

    if pred in _EMOTION_ADJECTIVES:
        if object_type in _PLACE_TYPES:
            return "place_preference"
        return "character_state"

    if subject_type in _CHARACTER_TYPES and object_type in _CHARACTER_TYPES:
        return "relationship_state"

    if subject_type in _CHARACTER_TYPES and object_type in _PLACE_TYPES:
        return "place_preference"

    if subject_type in _CHARACTER_TYPES and object_type in _OBJECT_TYPES:
        return "character_preference"

    if pred in {"knows", "believes", "understands", "remembers", "forgets"}:
        return "character_state"

    return "character_state"


def _family_role_label(predicate: str) -> str:
    role = predicate[: -len("_of")].replace("_", "-")
    return role or predicate


def _verb_phrase_for_claim(predicate: str, *, polarity: bool) -> str:
    pred = predicate.strip().lower()
    if pred.endswith("s") and not pred.endswith("ss"):
        base = pred[:-1]
    elif pred.endswith("ed"):
        base = pred[:-2] if len(pred) > 3 else pred
    else:
        base = pred
    if polarity:
        return pred
    return f"does not {base}"


def build_claim_sentence(
    *,
    subject: str,
    predicate: str,
    target: str,
    polarity: bool,
) -> str:
    subj = (subject or "").strip()
    obj = (target or "").strip()
    pred = normalize_predicate(predicate)

    if pred.endswith(_FAMILY_PREDICATE_SUFFIX):
        role = _family_role_label(pred)
        if polarity:
            return f"{subj} is the {role} of {obj}."
        return f"{subj} is not the {role} of {obj}."

    if pred in _EMOTION_ADJECTIVES:
        if obj:
            if polarity:
                return f"{subj} is {pred} with {obj}."
            return f"{subj} is not {pred} with {obj}."
        if polarity:
            return f"{subj} is {pred}."
        return f"{subj} is not {pred}."

    verb = _verb_phrase_for_claim(pred, polarity=polarity)
    if obj:
        return f"{subj} {verb} {obj}."
    return f"{subj} {verb}."


def relation_to_claim_draft(
    relation: RelationCandidate,
    entity_candidates: list[EntityCandidate],
) -> ClaimDraft | None:
    """Map one RelationCandidate to a ClaimDraft, or None if invalid."""
    subject = (relation.subject_surface or "").strip()
    target = (relation.object_surface or "").strip()
    if not subject:
        return None

    predicate = normalize_predicate(relation.predicate_normalized or relation.predicate_raw)
    if not predicate:
        return None

    evidence = (relation.evidence_text or "").strip()
    subj_type = _entity_type_for_surface(subject, entity_candidates, evidence=evidence)
    obj_type = (
        _entity_type_for_surface(target, entity_candidates, evidence=evidence)
        if target
        else "concept"
    )

    claim_type = infer_claim_type(
        subject_type=subj_type,
        object_type=obj_type,
        predicate=predicate,
        evidence_text=evidence,
    )
    if claim_type not in CLAIM_TYPES:
        claim_type = "character_state"

    claim_text = build_claim_sentence(
        subject=subject,
        predicate=predicate,
        target=target,
        polarity=relation.polarity,
    )

    status = status_for_confidence(relation.confidence)
    canon: CanonLevel = "active"
    if predicate.endswith(_FAMILY_PREDICATE_SUFFIX) and relation.confidence >= 0.8:
        canon = "active"

    return ClaimDraft(
        subject=subject,
        subject_entity_id=relation.subject_entity_id,
        predicate=predicate,
        target=target,
        object_entity_id=relation.object_entity_id,
        claim_type=claim_type,
        claim=claim_text,
        polarity=relation.polarity,
        confidence=relation.confidence,
        evidence_text=evidence[:500] or claim_text[:200],
        start_char=relation.start_char,
        end_char=relation.end_char,
        chunk_index=relation.chunk_index,
        status=status,
        canon_level=canon,
    )


def relations_to_claim_drafts(
    relations: list[RelationCandidate],
    entity_candidates: list[EntityCandidate],
) -> list[ClaimDraft]:
    """Map relation candidates to deduplicated claim drafts."""
    seen: set[tuple[str, str, str, str, bool]] = set()
    out: list[ClaimDraft] = []
    for rel in relations:
        draft = relation_to_claim_draft(rel, entity_candidates)
        if draft is None:
            continue
        key = (
            draft.subject.lower(),
            draft.claim_type.lower(),
            draft.predicate.lower(),
            draft.target.lower(),
            draft.polarity,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(draft)
    return sorted(out, key=lambda d: (d.chunk_index, d.start_char))


def claim_draft_to_extracted(draft: ClaimDraft) -> ExtractedClaim:
    """Convert a FASTUS ClaimDraft to ExtractedClaim for merge/compare paths."""
    return ExtractedClaim(
        subject=draft.subject,
        claim_type=draft.claim_type,
        predicate=draft.predicate,
        target=draft.target,
        claim=draft.claim,
        polarity=draft.polarity,
        confidence=draft.confidence,
        canon_level=draft.canon_level,
        evidence=draft.evidence_text,
        chunk_index=draft.chunk_index,
        generation_origin="structural",
    )
