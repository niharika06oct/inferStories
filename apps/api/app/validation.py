from sqlalchemy.orm import Session

from app.models import Claim, Scene, ValidationIssue


def validate_scene_claims(
    db: Session, scene: Scene, new_claims: list[Claim]
) -> list[ValidationIssue]:
    """
    Contradiction rule:
    If older claim has same (subject, predicate) but different object,
    it's a contradiction. If either side is major plotline => severity high.
    """
    issues: list[ValidationIssue] = []
    for claim in new_claims:
        older_conflicts = (
            db.query(Claim)
            .join(Scene, Scene.id == Claim.scene_id)
            .filter(
                Claim.story_id == scene.story_id,
                Scene.scene_number < scene.scene_number,
                Claim.subject == claim.subject,
                Claim.predicate == claim.predicate,
                Claim.claim_object != claim.claim_object,
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
    return issues
