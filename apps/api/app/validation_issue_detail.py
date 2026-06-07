"""FASTUS Stage 9 — structured continuity issue detail (evidence + explanation + fix).

Enriches validation issues so writers see both supporting quotes, a clear
explanation, and an actionable suggested fix — not only a rule message.

Relevant reading: FASTUS §10 Validation Engine; AIMA — logical agents.
"""

from __future__ import annotations

from app.continuity_judge import ContinuityCandidate, ContinuityJudgment
from app.models import Claim


def claim_evidence_quote(claim: Claim) -> str:
    """Best available prose quote for a claim (evidence preferred)."""
    evidence = (claim.evidence_text or "").strip()
    if evidence:
        return evidence[:500]
    return (claim.claim_text or "").strip()[:500]


def format_claim_fact(claim: Claim) -> str:
    """Human-readable triple, marking negated facts."""
    triple = (
        f"{claim.subject} {claim.predicate} {claim.claim_object}".strip()
    )
    if getattr(claim, "polarity", True) is False:
        return f"NOT ({triple})"
    return triple


def build_evidence_comparison(old_claim: Claim, new_claim: Claim) -> str:
    """Side-by-side evidence summary for the writer."""
    old_ev = claim_evidence_quote(old_claim)
    new_ev = claim_evidence_quote(new_claim)
    if old_ev and new_ev:
        return f'Earlier: "{old_ev}" → Now: "{new_ev}"'
    if old_ev:
        return f'Earlier: "{old_ev}"'
    if new_ev:
        return f'Now: "{new_ev}"'
    return ""


def build_explanation(
    candidate: ContinuityCandidate,
    judgment: ContinuityJudgment,
) -> str:
    """Structured explanation beyond the short issue message."""
    old = candidate.old_claim
    new = candidate.new_claim
    old_fact = format_claim_fact(old)
    new_fact = format_claim_fact(new)

    if candidate.conflict_kind == "polarity_flip":
        return (
            f"The same fact appears asserted and negated: "
            f"'{old_fact}' conflicts with '{new_fact}'. "
            f"{judgment.reason}"
        )
    if candidate.conflict_kind == "exclusive_object":
        return (
            f"Exclusive fact '{new.predicate}' cannot hold two values at once: "
            f"was '{old.claim_object}', now '{new.claim_object}'. "
            f"{judgment.reason}"
        )
    if candidate.conflict_kind == "predicate_opposition":
        return (
            f"Opposite relationship stances on the same pair: "
            f"earlier '{old.predicate}' vs now '{new.predicate}'. "
            f"{judgment.reason}"
        )
    return judgment.reason or candidate.rule_reason


def build_suggested_fix(candidate: ContinuityCandidate) -> str:
    """Actionable guidance for resolving the continuity issue."""
    old = candidate.old_claim
    new = candidate.new_claim

    if candidate.conflict_kind == "polarity_flip":
        return (
            "Decide which version is canon. If the negation is correct, deprecate "
            f"or reject the earlier claim ('{old.subject} {old.predicate} "
            f"{old.claim_object}') or add bridging prose that explains the reversal."
        )
    if candidate.conflict_kind == "exclusive_object":
        return (
            f"Pick one value as canon for '{new.predicate}' "
            f"({old.claim_object!r} vs {new.claim_object!r}), or add a scene "
            "that explains the change (move, breakup, revelation, etc.)."
        )
    if candidate.conflict_kind == "predicate_opposition":
        if candidate.rule_classification == "soft_tension":
            return (
                "If this is intentional emotional progression, add a bridging beat "
                f"between '{old.predicate}' and '{new.predicate}'. Otherwise adjust "
                "one claim or mark the earlier stance as superseded."
            )
        return (
            f"Reconcile '{old.predicate}' and '{new.predicate}' on "
            f"{new.subject} + {new.claim_object}: change one claim, or add prose "
            "that justifies the shift."
        )
    return (
        "Review both claims against the manuscript and update claim status "
        "(approve, reject, or deprecate) once you decide which is canon."
    )
