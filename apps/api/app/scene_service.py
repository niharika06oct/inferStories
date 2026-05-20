"""Save chapters and run automatic claim extraction."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extraction import extract_claims_from_text, replace_extracted_claims_for_scene
from app.extraction.schema import ExtractionResult
from app.models import Claim, Scene, ValidationIssue
from app.schemas import ClaimIn, SceneExtractionOut
from app.validation import validate_scene_claims


def _manual_claim_row(story_id: int, scene_id: int, c: ClaimIn) -> Claim:
    return Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=c.subject.strip(),
        predicate=c.predicate.strip(),
        claim_object=c.object.strip(),
        claim_type=c.claim_type or c.predicate.strip(),
        claim_text=c.claim_text or f"{c.subject} {c.predicate} {c.object}".strip(),
        confidence=c.confidence if c.confidence is not None else 1.0,
        canon_level=c.canon_level or "active",
        status="approved",
        evidence_text=c.evidence_text,
        source="manual",
        is_major_plotline=c.is_major_plotline,
    )


def _extraction_summary(result: ExtractionResult, rows: list[Claim]) -> SceneExtractionOut:
    needs_review = sum(1 for r in rows if r.status == "needs_review")
    suggested = sum(1 for r in rows if r.status == "suggested")
    approved = sum(1 for r in rows if r.status == "approved")
    return SceneExtractionOut(
        source=result.source,
        chunk_count=result.chunk_count,
        word_count=result.word_count,
        claim_count=len(rows),
        approved_count=approved,
        needs_review_count=needs_review,
        suggested_count=suggested,
    )


def save_scene_with_extraction(
    db: Session,
    scene: Scene,
    manual_claims: list[ClaimIn],
    *,
    run_extraction: bool = True,
) -> tuple[list[Claim], SceneExtractionOut | None]:
    """
    Replace claims for a scene: optional manual rows, then auto-extraction from text.
    Runs validation against approved canon only.
    """
    db.query(ValidationIssue).filter(ValidationIssue.scene_id == scene.id).delete(
        synchronize_session=False
    )
    db.query(Claim).filter(Claim.scene_id == scene.id).delete(synchronize_session=False)

    manual_rows: list[Claim] = []
    for c in manual_claims:
        if not c.subject.strip() or not c.predicate.strip() or not c.object.strip():
            continue
        row = _manual_claim_row(scene.story_id, scene.id, c)
        db.add(row)
        manual_rows.append(row)

    db.flush()

    extraction_out: SceneExtractionOut | None = None
    extracted_rows: list[Claim] = []
    if run_extraction and scene.text.strip():
        result = extract_claims_from_text(scene.text)
        extracted_rows = replace_extracted_claims_for_scene(db, scene, result.claims)
        extraction_out = _extraction_summary(result, extracted_rows)

    all_rows = manual_rows + extracted_rows
    validate_scene_claims(db, scene, all_rows)
    return all_rows, extraction_out
