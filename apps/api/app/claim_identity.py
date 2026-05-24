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


def compute_source_hash(
    subject: str,
    claim_type: str,
    target: str,
) -> str:
    """Deterministic key: same fact re-found on re-analyze maps to one row."""
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
) -> str:
    """Hash for a persisted Claim (predicate may be claim_type for extracted rows)."""
    ct = (claim_type or predicate or "").strip()
    return compute_source_hash(subject, ct, claim_object)
