"""Stable claim identity for merge-on-re-extract."""

from __future__ import annotations

import hashlib

# Removed on chapter re-analyze; approved/canonized memory is kept.
REPLACABLE_STATUSES: tuple[str, ...] = (
    "suggested",
    "needs_review",
    "rejected",
    "deprecated",
)

PRESERVED_STATUSES: tuple[str, ...] = ("approved", "canonized")


def _norm_part(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def compute_entity_source_hash(
    subject_entity_id: int,
    predicate: str,
    object_entity_id: int | None,
    claim_type: str,
) -> str:
    """Hash on canonical entity IDs + semantic predicate + claim category."""
    obj_part = str(object_entity_id) if object_entity_id else ""
    key = "|".join(
        (
            str(subject_entity_id),
            _norm_part(predicate),
            obj_part,
            _norm_part(claim_type),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def compute_source_hash(
    subject: str,
    claim_type: str,
    target: str,
) -> str:
    """Legacy string hash (pre-entity rows)."""
    key = "|".join(
        (
            _norm_part(subject),
            _norm_part(claim_type),
            _norm_part(target),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def source_hash_for_claim_row(
    subject: str,
    predicate: str,
    claim_object: str,
    claim_type: str | None,
    *,
    subject_entity_id: int | None = None,
    object_entity_id: int | None = None,
) -> str:
    if subject_entity_id is not None:
        return compute_entity_source_hash(
            subject_entity_id,
            predicate,
            object_entity_id,
            (claim_type or "").strip(),
        )
    ct = (claim_type or predicate or "").strip()
    return compute_source_hash(subject, ct, claim_object)
