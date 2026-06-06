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

# Earlier chapters: only accepted story memory counts as canon.
PAST_CANON_STATUSES = ("approved", "canonized")

# Current chapter: check accepted + pending review; never rejected.
CURRENT_SCENE_CHECK_STATUSES = ("approved", "canonized", "suggested", "needs_review")

# Back-compat alias for callers/tests referring to canon rows.
CANON_STATUSES = PAST_CANON_STATUSES


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
) -> ValidationIssue:
    offset, anchor_text, anchor_length = continuity_anchor_in_scene(
        scene.text or "", claim
    )
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
    )


def _maybe_add_issue(
    db: Session,
    issues: list[ValidationIssue],
    *,
    candidate: ContinuityCandidate,
) -> None:
    judgment = judge_continuity_candidate(candidate)
    if not should_show_judgment(judgment):
        return
    issue = _issue_row(
        scene=candidate.scene,
        claim=candidate.new_claim,
        old_claim=candidate.old_claim,
        severity=candidate.severity,
        message=candidate.message,
        judgment=judgment,
    )
    db.add(issue)
    issues.append(issue)


def validate_scene_claims(
    db: Session, scene: Scene, new_claims: list[Claim]
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
            if not _same_subject(claim, old_claim):
                continue
            op = _continuity_predicate(old_claim)
            oo = _norm(old_claim.claim_object)

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
                )

            if _same_object(claim, old_claim) and _different_predicates_are_conflict(
                op, np
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
                )

    return issues
