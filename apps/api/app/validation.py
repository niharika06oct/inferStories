from sqlalchemy.orm import Session

from app.entity_registry import _CLAIM_TYPE_SLUGS, infer_predicate_from_claim
from app.models import Claim, Scene, ValidationIssue

# Only approved claims participate in canon validation.
CANON_STATUSES = ("approved", "canonized")


def _norm(s: str) -> str:
    """Case- and whitespace-insensitive comparison key for claims."""
    return " ".join((s or "").strip().lower().split())


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


def _same_subject(a: Claim, b: Claim) -> bool:
    if a.subject_entity_id and b.subject_entity_id:
        return a.subject_entity_id == b.subject_entity_id
    return _norm(a.subject) == _norm(b.subject)


def _same_object(a: Claim, b: Claim) -> bool:
    if a.object_entity_id and b.object_entity_id:
        return a.object_entity_id == b.object_entity_id
    return _norm(a.claim_object) == _norm(b.claim_object)


def validate_scene_claims(
    db: Session, scene: Scene, new_claims: list[Claim]
) -> list[ValidationIssue]:
    """
    Rules (earlier scene = lower scene_number):

    1) Same subject + predicate, different object → contradiction.
    2) Same subject + object, different predicate → incompatible relationship.

    Uses entity IDs when present; falls back to normalized strings.
    """
    issues: list[ValidationIssue] = []

    older_claims = (
        db.query(Claim)
        .join(Scene, Scene.id == Claim.scene_id)
        .filter(
            Claim.story_id == scene.story_id,
            Scene.scene_number < scene.scene_number,
            Claim.status.in_(CANON_STATUSES),
        )
        .all()
    )

    for claim in new_claims:
        if claim.status not in CANON_STATUSES:
            continue

        np = _effective_predicate(claim)
        no = _norm(claim.claim_object)

        for old_claim in older_claims:
            if not _same_subject(claim, old_claim):
                continue
            op = _effective_predicate(old_claim)
            oo = _norm(old_claim.claim_object)

            if np == op and no != oo:
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

            if _same_object(claim, old_claim) and np != op:
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
