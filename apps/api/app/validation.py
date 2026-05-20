from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Claim, Scene, ValidationIssue

# Only approved claims participate in canon validation.
CANON_STATUSES = ("approved", "canonized")


def _norm(s: str) -> str:
    """Case- and whitespace-insensitive comparison key for claims."""
    return " ".join((s or "").strip().lower().split())


def validate_scene_claims(
    db: Session, scene: Scene, new_claims: list[Claim]
) -> list[ValidationIssue]:
    """
    Rules (earlier scene = lower scene_number):

    1) Same normalized (subject, predicate), different object → contradiction.
    2) Same normalized (subject, object), different predicate → incompatible
       statements about the same relationship (e.g. "towards" vs "away from").

    If either side is major plotline => severity high.
    """
    issues: list[ValidationIssue] = []
    subj_key = func.lower(func.trim(Claim.subject))
    pred_key = func.lower(func.trim(Claim.predicate))
    obj_key = func.lower(func.trim(Claim.claim_object))

    for claim in new_claims:
        if claim.status not in CANON_STATUSES:
            continue

        ns, np, no = _norm(claim.subject), _norm(claim.predicate), _norm(claim.claim_object)

        older_conflicts = (
            db.query(Claim)
            .join(Scene, Scene.id == Claim.scene_id)
            .filter(
                Claim.story_id == scene.story_id,
                Scene.scene_number < scene.scene_number,
                Claim.status.in_(CANON_STATUSES),
                subj_key == ns,
                pred_key == np,
                obj_key != no,
            )
            .all()
        )
        for old_claim in older_conflicts:
            is_major = claim.is_major_plotline or old_claim.is_major_plotline
            severity = "high" if is_major else "medium"
            msg = (
                f"Scene {scene.scene_number} contradicts earlier fact: "
                f"{claim.subject} {claim.predicate} was '{old_claim.claim_object}', "
                f"now '{claim.claim_object}'."
            )
            if is_major:
                msg += " This conflicts with a major plotline relationship/fact."
            issue = ValidationIssue(
                story_id=scene.story_id,
                scene_id=scene.id,
                severity=severity,
                message=msg,
                conflicting_claim_id=old_claim.id,
            )
            db.add(issue)
            issues.append(issue)

        predicate_conflicts = (
            db.query(Claim)
            .join(Scene, Scene.id == Claim.scene_id)
            .filter(
                Claim.story_id == scene.story_id,
                Scene.scene_number < scene.scene_number,
                Claim.status.in_(CANON_STATUSES),
                subj_key == ns,
                obj_key == no,
                pred_key != np,
            )
            .all()
        )
        for old_claim in predicate_conflicts:
            is_major = claim.is_major_plotline or old_claim.is_major_plotline
            severity = "high" if is_major else "medium"
            msg = (
                f"Scene {scene.scene_number} conflicts with an earlier claim about "
                f"{claim.subject} and {claim.claim_object}: "
                f"earlier '{old_claim.predicate}', now '{claim.predicate}'."
            )
            if is_major:
                msg += " This conflicts with a major plotline relationship/fact."
            issue = ValidationIssue(
                story_id=scene.story_id,
                scene_id=scene.id,
                severity=severity,
                message=msg,
                conflicting_claim_id=old_claim.id,
            )
            db.add(issue)
            issues.append(issue)

    return issues
