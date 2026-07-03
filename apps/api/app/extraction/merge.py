"""FASTUS Stage 7 — Polarity-aware claim merge and temporal state transitions.

Merge identity uses subject_entity_id + predicate + object_entity_id + polarity +
claim_type (via source_hash). Supports object transitions on relational predicates
and confidence history on reinforcement.

Relevant reading: DDIA Ch. 2–3; AIMA — inference with negation as distinct facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.claim_identity import predicate_merge_key
from app.models import Claim

# Predicates where a new object closes the prior open fact (state transition).
_OBJECT_TRANSITION_PREDICATES = frozenset(
    {
        "trusts",
        "distrusts",
        "loves",
        "hates",
        "fears",
        "misses",
        "partner_of",
        "married_to",
        "boyfriend_of",
        "girlfriend_of",
        "cares_for",
        "lives_in",
        "lives_at",
        "located_in",
    }
)


@dataclass
class MergeStats:
    inserted: int = 0
    updated: int = 0
    transitions: int = 0
    events: list[dict[str, str]] = field(default_factory=list)


def entity_pair_merge_key(
    subject_entity_id: int,
    object_entity_id: int,
    predicate: str,
    *,
    polarity: bool,
) -> tuple[int, int, str, bool]:
    """Entity-aware merge key including polarity (negation is a distinct fact)."""
    return (
        subject_entity_id,
        object_entity_id,
        predicate_merge_key(predicate),
        polarity,
    )


def subject_predicate_merge_key(
    subject_entity_id: int,
    predicate: str,
    *,
    polarity: bool,
) -> tuple[int, str, bool]:
    return (subject_entity_id, predicate_merge_key(predicate), polarity)


def allows_object_transition(predicate: str) -> bool:
    return predicate_merge_key(predicate) in _OBJECT_TRANSITION_PREDICATES


def append_confidence_history(
    row: Claim,
    *,
    confidence: float,
    scene_id: int,
    version: int,
) -> None:
    history: list[dict[str, float | int]] = []
    raw = getattr(row, "confidence_history", None)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                history = parsed
        except (json.JSONDecodeError, TypeError):
            history = []
    history.append(
        {
            "version": version,
            "confidence": round(float(confidence), 4),
            "scene_id": scene_id,
        }
    )
    row.confidence_history = json.dumps(history)


def init_confidence_history(
    row: Claim,
    *,
    confidence: float,
    scene_id: int,
) -> None:
    row.confidence_history = json.dumps(
        [{"version": 1, "confidence": round(float(confidence), 4), "scene_id": scene_id}]
    )


def find_open_transition_prior(
    by_subject_predicate: dict[tuple[int, str, bool], Claim],
    *,
    subject_entity_id: int,
    object_entity_id: int | None,
    predicate: str,
    polarity: bool,
) -> Claim | None:
    """Find an active claim with same subject+predicate+polarity but a different object."""
    if not object_entity_id or not allows_object_transition(predicate):
        return None
    key = subject_predicate_merge_key(
        subject_entity_id, predicate, polarity=polarity
    )
    prior = by_subject_predicate.get(key)
    if prior is None:
        return None
    if prior.object_entity_id == object_entity_id:
        return None
    if getattr(prior, "valid_until_scene", None) is not None:
        return None
    return prior


def register_subject_predicate_index(
    by_subject_predicate: dict[tuple[int, str, bool], Claim],
    row: Claim,
) -> None:
    if not row.subject_entity_id:
        return
    if getattr(row, "valid_until_scene", None) is not None:
        return
    key = subject_predicate_merge_key(
        row.subject_entity_id,
        row.predicate or "",
        polarity=getattr(row, "polarity", True),
    )
    by_subject_predicate[key] = row


def record_merge_event(
    stats: MergeStats | None,
    *,
    event: str,
    message: str,
    detail: dict[str, str] | None = None,
) -> None:
    if stats is None:
        return
    stats.events.append(
        {
            "stage": "7",
            "event": event,
            "message": message,
            "detail": detail or {},
        }
    )
