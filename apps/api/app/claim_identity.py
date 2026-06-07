"""Stable claim identity for merge-on-re-extract."""

from __future__ import annotations

import hashlib

# Removed on chapter re-analyze; user-decided rows are kept (see MERGE_PRESERVE_STATUSES).
REPLACABLE_STATUSES: tuple[str, ...] = (
    "suggested",
    "needs_review",
    "deprecated",
)

# Canon validation only — rejected is not canon.
PRESERVED_STATUSES: tuple[str, ...] = ("approved", "canonized")

# Kept on re-analyze; merge updates text but preserves status (approved or rejected).
MERGE_PRESERVE_STATUSES: tuple[str, ...] = (
    "approved",
    "canonized",
    "rejected",
)


def _norm_part(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def norm_evidence(value: str) -> str:
    """Normalize quote/evidence for merge-on-re-extract."""
    return _norm_part(value).strip("\"'“”‘’")


_PREDICATE_ALIASES: dict[str, str] = {
    "love": "loves",
    "loves": "loves",
    "loved": "loves",
    "hate": "hates",
    "hates": "hates",
    "hated": "hates",
    "trust": "trusts",
    "trusts": "trusts",
    "trusted": "trusts",
    "distrust": "distrusts",
    "distrusts": "distrusts",
    "distrusted": "distrusts",
    "fear": "fears",
    "fears": "fears",
    "feared": "fears",
    "desire": "desires",
    "desires": "desires",
    "desired": "desires",
}


def predicate_merge_key(predicate: str) -> str:
    p = _norm_part(predicate).replace(" ", "_")
    return _PREDICATE_ALIASES.get(p, p)


def _polarity_suffix(polarity: bool) -> tuple[str, ...]:
    """A negated fact is a distinct claim identity from its asserted form.

    Positive claims keep their historical key (no suffix) so existing hashes stay stable.
    """
    return () if polarity else ("neg",)


def compute_entity_source_hash(
    subject_entity_id: int,
    predicate: str,
    object_entity_id: int | None,
    claim_type: str,
    *,
    polarity: bool = True,
) -> str:
    """Hash on canonical entity IDs + semantic predicate + claim category + polarity."""
    obj_part = str(object_entity_id) if object_entity_id else ""
    key = "|".join(
        (
            str(subject_entity_id),
            _norm_part(predicate),
            obj_part,
            _norm_part(claim_type),
            *_polarity_suffix(polarity),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def compute_source_hash(
    subject: str,
    claim_type: str,
    target: str,
    *,
    polarity: bool = True,
) -> str:
    """Legacy string hash (pre-entity rows)."""
    key = "|".join(
        (
            _norm_part(subject),
            _norm_part(claim_type),
            _norm_part(target),
            *_polarity_suffix(polarity),
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
    polarity: bool = True,
) -> str:
    if subject_entity_id is not None:
        return compute_entity_source_hash(
            subject_entity_id,
            predicate,
            object_entity_id,
            (claim_type or "").strip(),
            polarity=polarity,
        )
    ct = (claim_type or predicate or "").strip()
    return compute_source_hash(subject, ct, claim_object, polarity=polarity)
