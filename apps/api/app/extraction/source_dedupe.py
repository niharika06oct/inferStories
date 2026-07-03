"""Source-aware dedupe across LLM recall, FASTUS drafts, and regex layers."""

from __future__ import annotations

from app.extraction.schema import ExtractedClaim

_ORIGIN_PRIORITY = {
    "fastus": 4,
    "structural": 3,
    "family": 3,
    "llm": 2,
    "llm_recall": 1,
    "heuristic": 0,
}


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def claim_identity_key(claim: ExtractedClaim) -> tuple[str, str, str, str, bool]:
    return (
        _norm(claim.subject),
        _norm(claim.predicate).replace(" ", "_"),
        _norm(claim.target),
        _norm(claim.claim_type),
        claim.polarity,
    )


def _origin_rank(origin: str) -> int:
    return _ORIGIN_PRIORITY.get((origin or "").split("+")[0].strip(), 0)


def _best_evidence(a: ExtractedClaim, b: ExtractedClaim) -> str:
    """Prefer anchored FASTUS/regex evidence over LLM recall quotes."""
    if a.anchored and not b.anchored:
        return a.evidence
    if b.anchored and not a.anchored:
        return b.evidence
    if _origin_rank(a.generation_origin) >= _origin_rank(b.generation_origin):
        return a.evidence or b.evidence
    return b.evidence or a.evidence


def _merge_origins(a: ExtractedClaim, b: ExtractedClaim) -> tuple[str, list[str]]:
    origins: list[str] = []
    for c in (a, b):
        for part in (c.generation_origin or "").split("+"):
            p = part.strip()
            if p and p not in origins:
                origins.append(p)
        for sec in c.secondary_origins:
            if sec not in origins:
                origins.append(sec)
    origins.sort(key=_origin_rank, reverse=True)
    primary = origins[0] if origins else "unknown"
    label = "+".join(origins) if len(origins) > 1 else primary
    return label[:64], origins


def merge_duplicate_claims(a: ExtractedClaim, b: ExtractedClaim) -> ExtractedClaim:
    """Merge two claims with the same identity key."""
    origins_label, origins_list = _merge_origins(a, b)
    confidence = max(a.confidence, b.confidence)
    if a.anchored and b.anchored:
        confidence = min(1.0, (a.confidence + b.confidence) / 2 + 0.05)

    anchored = a.anchored or b.anchored
    review_status = "needs_review"
    if anchored and confidence >= 0.90:
        review_status = "suggested"
    elif not anchored:
        review_status = "needs_review"

    evidence = _best_evidence(a, b)
    claim_text = a.claim if len(a.claim) >= len(b.claim) else b.claim

    return a.model_copy(
        update={
            "confidence": confidence,
            "evidence": evidence,
            "claim": claim_text,
            "anchored": anchored,
            "generation_origin": origins_label,
            "secondary_origins": origins_list,
            "review_status": review_status,
        }
    )


def merge_source_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """Dedupe by subject+predicate+target+claim_type+polarity; merge metadata."""
    by_key: dict[tuple[str, str, str, str, bool], ExtractedClaim] = {}
    for claim in claims:
        key = claim_identity_key(claim)
        if key in by_key:
            by_key[key] = merge_duplicate_claims(by_key[key], claim)
        else:
            by_key[key] = claim
    return list(by_key.values())
