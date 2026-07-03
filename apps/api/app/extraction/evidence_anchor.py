"""Evidence anchoring for extracted claims (Option B FASTUS grounding)."""

from __future__ import annotations

import os
import re

from app.extraction.schema import ExtractedClaim
from app.validation_evidence import locate_claim_evidence_span

_UNANCHORED_CONFIDENCE_PENALTY = 0.15


def strict_anchoring_enabled() -> bool:
    return os.getenv("FASTUS_STRICT_ANCHORING", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def evidence_anchored_in_text(
    scene_text: str,
    *,
    evidence: str,
    claim_text: str = "",
) -> bool:
    """True when evidence or claim text appears in the passage (case-insensitive)."""
    text = (scene_text or "").strip()
    if not text:
        return False
    lowered = text.lower()
    for field in (evidence, claim_text):
        quote = (field or "").strip()
        if not quote:
            continue
        anchor = quote[:500]
        if lowered.find(anchor.lower()) >= 0:
            return True
        # Multi-sentence evidence: any sentence verbatim in passage counts as anchored.
        for sentence in re.split(r"(?<=[.!?])\s+", anchor):
            s = sentence.strip()
            if len(s) >= 12 and lowered.find(s.lower()) >= 0:
                return True
    return False


def apply_evidence_anchoring(
    claim: ExtractedClaim,
    chunk_text: str,
    *,
    importance: str = "medium",
) -> ExtractedClaim:
    """
    Set anchored flag, adjust confidence, and assign review_status.

    Unanchored claims go to needs_review unless strict anchoring drops them later.
    """
    off, length, matched = locate_claim_evidence_span(
        chunk_text,
        evidence_text=claim.evidence,
        claim_text=claim.claim,
        claim_object=claim.target,
        claim_subject=claim.subject,
    )
    evidence = claim.evidence
    anchored = evidence_anchored_in_text(
        chunk_text,
        evidence=claim.evidence,
        claim_text=claim.claim,
    )
    if off >= 0 and length > 0 and matched:
        evidence = matched
        anchored = True

    confidence = claim.confidence
    review_status = claim.review_status
    weak_evidence = len((evidence or "").strip()) < 20

    if weak_evidence and anchored:
        review_status = "needs_review"
        confidence = min(confidence, 0.75)

    if not anchored:
        confidence = max(0.0, confidence - _UNANCHORED_CONFIDENCE_PENALTY)
        review_status = "needs_review"
    elif confidence >= 0.90 and anchored:
        review_status = review_status or "suggested"
    elif confidence >= 0.65:
        review_status = review_status or "needs_review"
    else:
        review_status = review_status or "suggested"

    if importance == "high" and not anchored:
        review_status = "needs_review"

    return claim.model_copy(
        update={
            "anchored": anchored,
            "evidence": evidence,
            "confidence": confidence,
            "review_status": review_status,
            "importance": importance if importance in ("low", "medium", "high") else "medium",
        }
    )


def filter_unanchored_if_strict(claims: list[ExtractedClaim]) -> tuple[list[ExtractedClaim], int]:
    """Drop unanchored claims when FASTUS_STRICT_ANCHORING=1."""
    if not strict_anchoring_enabled():
        return claims, 0
    kept: list[ExtractedClaim] = []
    dropped = 0
    for c in claims:
        if c.anchored is False and c.generation_origin == "llm_recall":
            dropped += 1
            continue
        kept.append(c)
    return kept, dropped
