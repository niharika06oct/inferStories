from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.continuity_judge import (
    ContinuityCandidate,
    ContinuityJudgment,
    judge_continuity_candidate,
    should_show_judgment,
)
from app.entity_registry import _CLAIM_TYPE_SLUGS, infer_predicate_from_claim
from app.models import Claim, Scene, ValidationIssue
from app.validation_evidence import continuity_anchor_in_scene
from app.location_compatibility import (
    is_location_predicate,
    location_facts_compatible,
)
from app.validation_issue_detail import (
    build_evidence_comparison,
    build_explanation,
    build_suggested_fix,
    claim_evidence_quote,
)

# Earlier chapters: only accepted story memory counts as canon.
PAST_CANON_STATUSES = ("approved", "canonized")

# Current chapter: check accepted + pending review; never rejected.
CURRENT_SCENE_CHECK_STATUSES = ("approved", "canonized", "suggested", "needs_review")

# Back-compat alias for callers/tests referring to canon rows.
CANON_STATUSES = PAST_CANON_STATUSES

# Map positive predicates to their negated stance for opposition checks.
_POLARITY_NEGATED_PREDICATE: dict[str, str] = {
    "trusts": "distrusts",
    "trust": "distrust",
    "loves": "hates",
    "love": "hate",
    "likes": "dislikes",
    "like": "dislike",
}


@dataclass
class ValidationStats:
    """FASTUS Stage 8 — polarity-aware continuity validation instrumentation."""

    issues_raised: int = 0
    superseded_skipped: int = 0
    polarity_flips: int = 0
    events: list[dict[str, str]] = field(default_factory=list)


def record_validation_event(
    stats: ValidationStats | None,
    *,
    event: str,
    message: str,
    detail: dict[str, str] | None = None,
) -> None:
    if stats is None:
        return
    stats.events.append(
        {
            "stage": "9" if event == "issue_enriched" else "8",
            "event": event,
            "message": message,
            "detail": detail or {},
        }
    )


def _norm(s: str) -> str:
    """Case- and whitespace-insensitive comparison key for claims."""
    return " ".join((s or "").strip().lower().split())


def _predicate_key(predicate: str) -> str:
    """Normalize predicate labels across free text / snake_case variants."""
    return _norm(predicate).replace("_", " ")


def _effective_predicate(claim: Claim) -> str:
    p = _norm(claim.predicate)
    if p in _CLAIM_TYPE_SLUGS:
        return _norm(
            infer_predicate_from_claim(
                claim.claim_type or "",
                claim.claim_text or "",
            )
        )
    return p


def _continuity_predicate(claim: Claim) -> str:
    """
    Predicate used for continuity comparison.

    Extraction can over-label mild discomfort as "distrusts". For continuity,
    "It made me uncomfortable" should not become a trust/distrust contradiction
    unless the source text explicitly says trust/distrust.
    """
    p = _effective_predicate(claim)
    text = _norm(f"{claim.evidence_text or ''} {claim.claim_text or ''}")
    if p in {"distrusts", "distrust"} and "uncomfortable" in text:
        if not any(
            phrase in text
            for phrase in (
                "distrust",
                "did not trust",
                "does not trust",
                "don't trust",
                "didn't trust",
                "could not trust",
                "couldn't trust",
            )
        ):
            return "is uncomfortable with"
    return p


def _is_superseded(claim: Claim) -> bool:
    """Claims closed by Stage 7 state transitions are not active canon."""
    return getattr(claim, "valid_until_scene", None) is not None


def _stance_predicate(claim: Claim) -> str:
    """
    Predicate used for stance/opposition checks.

    A negated ``trusts`` claim is treated as ``distrusts`` so explicit opposition
    rules align with polarity without double-firing alongside polarity_flip.
    """
    p = _continuity_predicate(claim)
    if getattr(claim, "polarity", True) is False:
        return _POLARITY_NEGATED_PREDICATE.get(_predicate_key(p), p)
    return p


_NEGATIVE_STANCE = frozenset(
    {
        "dislikes",
        "dislike",
        "distrusts",
        "distrust",
        "dreads",
        "dread",
        "fears",
        "fear",
        "feels fear",
        "hostile",
        "is hostile",
        "hostile to",
        "hates",
        "hate",
        "detests",
        "detest",
        "worries about",
        "worried about",
    }
)

_POSITIVE_STANCE = frozenset(
    {
        "likes",
        "like",
        "loves",
        "love",
        "trusts",
        "trust",
        "cares for",
        "cares",
        "is comfortable with",
        "comfortable with",
        "is relieved about",
        "relieved about",
    }
)

_MILD_DISCOMFORT = frozenset({"is uncomfortable with", "uncomfortable with"})

_APPROACHING = frozenset(
    {"running towards", "runs towards", "moves toward", "approaches", "seeks"}
)
_AVOIDING = frozenset(
    {"running away from", "runs away from", "avoids", "avoiding", "fleeing"}
)

_EXPLICIT_OPPOSITES: frozenset[tuple[str, str]] = frozenset(
    {
        ("trusts", "distrusts"),
        ("trust", "distrust"),
        ("likes", "dislikes"),
        ("like", "dislike"),
        ("loves", "hates"),
        ("love", "hate"),
        ("loves", "detests"),
        ("love", "detest"),
        ("is alive", "is dead"),
        ("alive", "dead"),
        ("can", "cannot"),
    }
)

# Same subject + same predicate + different object is only a contradiction for
# facts that normally have one value at a time. Emotional predicates are not
# exclusive: Bella can distrust Charlie and Edward, or love Phoenix and Forks.
_EXCLUSIVE_OBJECT_PREDICATES = frozenset(
    {
        "is",
        "is from",
        "born in",
        "lives in",
        "lives at",
        "resides in",
        "works as",
        "is married to",
        "spouse of",
        "partner of",
        "moving to",
    }
)


def _same_stance_family(a: str, b: str) -> bool:
    return (a in _NEGATIVE_STANCE and b in _NEGATIVE_STANCE) or (
        a in _POSITIVE_STANCE and b in _POSITIVE_STANCE
    ) or (
        a in _MILD_DISCOMFORT and b in _MILD_DISCOMFORT
    )


def _are_explicit_opposites(a: str, b: str) -> bool:
    if (a, b) in _EXPLICIT_OPPOSITES or (b, a) in _EXPLICIT_OPPOSITES:
        return True
    if (a in _APPROACHING and b in _AVOIDING) or (
        b in _APPROACHING and a in _AVOIDING
    ):
        return True
    if (a in _POSITIVE_STANCE and b in _NEGATIVE_STANCE) or (
        b in _POSITIVE_STANCE and a in _NEGATIVE_STANCE
    ):
        # Opposite emotional polarity is a soft tension worth showing, but only
        # when it is about the same subject/object pair.
        return True
    return False


def _object_is_exclusive_value(value: str) -> bool:
    key = _norm(value)
    return key in {"nobody", "no one", "none", "nothing", "no-one"}


def _same_predicate_different_object_is_conflict(
    predicate: str, old_object: str, new_object: str
) -> bool:
    p = _predicate_key(predicate)
    return p in _EXCLUSIVE_OBJECT_PREDICATES or _object_is_exclusive_value(
        old_object
    ) or _object_is_exclusive_value(new_object)


def _different_predicates_are_conflict(old_predicate: str, new_predicate: str) -> bool:
    old_key = _predicate_key(old_predicate)
    new_key = _predicate_key(new_predicate)
    if old_key == new_key:
        return False
    if _same_stance_family(old_key, new_key):
        return False
    return _are_explicit_opposites(old_key, new_key)


def _same_subject(a: Claim, b: Claim) -> bool:
    if a.subject_entity_id and b.subject_entity_id:
        return a.subject_entity_id == b.subject_entity_id
    return _norm(a.subject) == _norm(b.subject)


def _same_object(a: Claim, b: Claim) -> bool:
    if a.object_entity_id and b.object_entity_id:
        return a.object_entity_id == b.object_entity_id
    return _norm(a.claim_object) == _norm(b.claim_object)


def _issue_row(
    *,
    scene: Scene,
    claim: Claim,
    old_claim: Claim,
    severity: str,
    message: str,
    judgment: ContinuityJudgment,
    candidate: ContinuityCandidate,
) -> ValidationIssue:
    offset, anchor_text, anchor_length = continuity_anchor_in_scene(
        scene.text or "", claim
    )
    conflicting_evidence = claim_evidence_quote(old_claim) or None
    current_evidence = claim_evidence_quote(claim) or None
    comparison = build_evidence_comparison(old_claim, claim) or None
    explanation = build_explanation(candidate, judgment)
    suggested_fix = build_suggested_fix(candidate)
    return ValidationIssue(
        story_id=scene.story_id,
        scene_id=scene.id,
        severity=severity,
        message=message,
        conflicting_claim_id=old_claim.id,
        current_claim_id=claim.id,
        text_offset=offset,
        anchor_text=anchor_text or None,
        anchor_length=anchor_length,
        resolution_status="open",
        judge_source=judgment.source,
        judge_classification=judgment.classification,
        judge_confidence=judgment.confidence,
        judge_reason=judgment.reason or None,
        conflict_kind=candidate.conflict_kind,
        conflicting_evidence_text=conflicting_evidence,
        current_evidence_text=current_evidence,
        evidence_comparison=comparison,
        explanation=explanation,
        suggested_fix=suggested_fix,
    )


def _maybe_add_issue(
    db: Session,
    issues: list[ValidationIssue],
    *,
    candidate: ContinuityCandidate,
    validation_stats: ValidationStats | None = None,
) -> None:
    judgment = judge_continuity_candidate(candidate)
    if not should_show_judgment(judgment):
        return
    if validation_stats is not None:
        validation_stats.issues_raised += 1
        if candidate.conflict_kind == "polarity_flip":
            validation_stats.polarity_flips += 1
        record_validation_event(
            validation_stats,
            event=candidate.conflict_kind,
            message=candidate.message,
            detail={
                "severity": candidate.severity,
                "classification": judgment.classification,
                "stage": "9",
            },
        )
        record_validation_event(
            validation_stats,
            event="issue_enriched",
            message="Attached evidence quotes and suggested fix",
            detail={
                "conflict_kind": candidate.conflict_kind,
                "has_evidence": "true"
                if claim_evidence_quote(candidate.old_claim)
                or claim_evidence_quote(candidate.new_claim)
                else "false",
            },
        )
    issue = _issue_row(
        scene=candidate.scene,
        claim=candidate.new_claim,
        old_claim=candidate.old_claim,
        severity=candidate.severity,
        message=candidate.message,
        judgment=judgment,
        candidate=candidate,
    )
    db.add(issue)
    issues.append(issue)


def validate_scene_claims(
    db: Session,
    scene: Scene,
    new_claims: list[Claim],
    *,
    validation_stats: ValidationStats | None = None,
) -> list[ValidationIssue]:
    """
    Compare current-chapter claims against accepted memory from earlier scenes.

    - Past scenes: only approved / canonized claims.
    - Current scene (new_claims): approved, canonized, suggested, needs_review.
      Rejected and deprecated claims are skipped.

    Rules (earlier scene = lower scene_number):

    1) Same subject + exclusive predicate, different object → contradiction.
    2) Same subject + object, explicitly incompatible predicate → conflict.

    Uses entity IDs when present; falls back to normalized strings. No LLM calls.
    """
    issues: list[ValidationIssue] = []

    older_claims = (
        db.query(Claim)
        .join(Scene, Scene.id == Claim.scene_id)
        .filter(
            Claim.story_id == scene.story_id,
            Scene.scene_number < scene.scene_number,
            Claim.status.in_(PAST_CANON_STATUSES),
        )
        .all()
    )

    for claim in new_claims:
        if claim.status not in CURRENT_SCENE_CHECK_STATUSES:
            continue

        np = _continuity_predicate(claim)
        no = _norm(claim.claim_object)

        for old_claim in older_claims:
            if _is_superseded(old_claim):
                if validation_stats is not None:
                    validation_stats.superseded_skipped += 1
                continue
            if not _same_subject(claim, old_claim):
                continue
            op = _continuity_predicate(old_claim)
            oo = _norm(old_claim.claim_object)

            new_polarity = getattr(claim, "polarity", True)
            old_polarity = getattr(old_claim, "polarity", True)
            if np == op and _same_object(claim, old_claim) and (
                new_polarity != old_polarity
            ):
                is_major = claim.is_major_plotline or old_claim.is_major_plotline
                severity = "high" if is_major else "medium"
                asserted, denied = (
                    (old_claim, claim) if old_polarity else (claim, old_claim)
                )
                msg = (
                    f"Scene {scene.scene_number} reverses an earlier fact: "
                    f"'{asserted.subject} {asserted.predicate} {asserted.claim_object}' "
                    f"is now negated."
                )
                if is_major:
                    msg += " This conflicts with a major plotline relationship/fact."
                _maybe_add_issue(
                    db,
                    issues,
                    candidate=ContinuityCandidate(
                        scene=scene,
                        new_claim=claim,
                        old_claim=old_claim,
                        severity=severity,
                        message=msg,
                        rule_classification="hard_contradiction",
                        rule_reason=(
                            "The same subject/predicate/object is asserted in one "
                            "scene and negated in another (polarity flip)."
                        ),
                        conflict_kind="polarity_flip",
                    ),
                    validation_stats=validation_stats,
                )
                continue

            location_pair = is_location_predicate(np) and is_location_predicate(op)
            if no != oo and location_pair and location_facts_compatible(
                db,
                old_object=old_claim.claim_object,
                new_object=claim.claim_object,
                old_object_entity_id=old_claim.object_entity_id,
                new_object_entity_id=claim.object_entity_id,
                old_evidence=(old_claim.evidence_text or old_claim.claim_text or ""),
                new_evidence=(claim.evidence_text or claim.claim_text or ""),
            ):
                continue

            if np == op and no != oo and _same_predicate_different_object_is_conflict(
                np, old_claim.claim_object, claim.claim_object
            ):
                is_major = claim.is_major_plotline or old_claim.is_major_plotline
                severity = "high" if is_major else "medium"
                msg = (
                    f"Scene {scene.scene_number} contradicts earlier fact: "
                    f"{claim.subject} {claim.predicate} was '{old_claim.claim_object}', "
                    f"now '{claim.claim_object}'."
                )
                if is_major:
                    msg += " This conflicts with a major plotline relationship/fact."
                _maybe_add_issue(
                    db,
                    issues,
                    candidate=ContinuityCandidate(
                        scene=scene,
                        new_claim=claim,
                        old_claim=old_claim,
                        severity=severity,
                        message=msg,
                        rule_classification="hard_contradiction",
                        rule_reason=(
                            "The same exclusive fact has a different value "
                            "in an earlier accepted claim."
                        ),
                        conflict_kind="exclusive_object",
                    ),
                    validation_stats=validation_stats,
                )

            old_stance = _stance_predicate(old_claim)
            new_stance = _stance_predicate(claim)
            if _same_object(claim, old_claim) and _different_predicates_are_conflict(
                old_stance, new_stance
            ):
                is_major = claim.is_major_plotline or old_claim.is_major_plotline
                severity = "high" if is_major else "medium"
                msg = (
                    f"Scene {scene.scene_number} conflicts with an earlier claim about "
                    f"{claim.subject} and {claim.claim_object}: "
                    f"earlier '{old_claim.predicate}', now '{claim.predicate}'."
                )
                if is_major:
                    msg += " This conflicts with a major plotline relationship/fact."
                _maybe_add_issue(
                    db,
                    issues,
                    candidate=ContinuityCandidate(
                        scene=scene,
                        new_claim=claim,
                        old_claim=old_claim,
                        severity=severity,
                        message=msg,
                        rule_classification="soft_tension",
                        rule_reason=(
                            "The later claim uses an explicitly opposite "
                            "relationship/emotional predicate for the same pair."
                        ),
                        conflict_kind="predicate_opposition",
                    ),
                    validation_stats=validation_stats,
                )

    if validation_stats is not None and validation_stats.issues_raised == 0:
        record_validation_event(
            validation_stats,
            event="validation_clean",
            message=f"No continuity issues for scene {scene.scene_number}",
            detail={"superseded_skipped": str(validation_stats.superseded_skipped)},
        )

    return issues
