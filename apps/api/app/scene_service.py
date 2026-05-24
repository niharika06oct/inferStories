"""Save chapters and run automatic claim extraction."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extraction import extract_claims_from_text
from app.extraction.persist import (
    delete_replaceable_scene_claims,
    merge_extracted_claims_for_scene,
)
from app.extraction.schema import ExtractionResult
from app.claim_identity import source_hash_for_claim_row
from app.models import Claim, Scene, ValidationIssue
from app.schemas import ClaimIn, SceneExtractionOut
from app.validation import validate_scene_claims


def _manual_claim_row(story_id: int, scene_id: int, c: ClaimIn) -> Claim:
    subject = c.subject.strip()
    predicate = c.predicate.strip()
    obj = c.object.strip()
    claim_type = c.claim_type or predicate
    return Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=subject,
        predicate=predicate,
        claim_object=obj,
        claim_type=claim_type,
        claim_text=c.claim_text or f"{subject} {predicate} {obj}".strip(),
        confidence=c.confidence if c.confidence is not None else 1.0,
        canon_level=c.canon_level or "active",
        status="approved",
        evidence_text=c.evidence_text,
        source="manual",
        is_major_plotline=c.is_major_plotline,
        source_hash=source_hash_for_claim_row(subject, predicate, obj, claim_type),
        claim_version=1,
    )


def _extraction_summary(result: ExtractionResult, rows: list[Claim]) -> SceneExtractionOut:
    needs_review = sum(1 for r in rows if r.status == "needs_review")
    suggested = sum(1 for r in rows if r.status == "suggested")
    approved = sum(1 for r in rows if r.status == "approved")
    from app.schemas import ChunkExtractionDebugOut

    return SceneExtractionOut(
        source=result.source,
        chunk_count=result.chunk_count,
        word_count=result.word_count,
        claim_count=len(rows),
        approved_count=approved,
        needs_review_count=needs_review,
        suggested_count=suggested,
        error=result.error,
        duration_ms=result.duration_ms,
        openai_attempted=result.openai_attempted,
        fallback_used=result.fallback_used,
        large_chapter_warning=result.large_chapter_warning,
        structural_entity_count=result.structural_entity_count,
        chunks=[
            ChunkExtractionDebugOut(
                chunk_index=c.chunk_index,
                word_count=c.word_count,
                openai_attempted=c.openai_attempted,
                openai_ok=c.openai_ok,
                fallback_used=c.fallback_used,
                structural_claims=c.structural_claims,
                llm_claims=c.llm_claims,
                entities=c.entities,
            )
            for c in result.chunks
        ],
    )


def save_scene_with_extraction(
    db: Session,
    scene: Scene,
    manual_claims: list[ClaimIn],
    *,
    run_extraction: bool = True,
) -> tuple[list[Claim], SceneExtractionOut | None]:
    """
    Save chapter claims: keep approved/canonized memory on re-analyze, refresh the rest.

    Re-extraction deletes only suggested / needs_review / rejected / deprecated rows,
    then merges new extractions by source_hash (updates approved matches in place).
    """
    db.query(ValidationIssue).filter(ValidationIssue.scene_id == scene.id).delete(
        synchronize_session=False
    )

    if manual_claims:
        # Explicit claim payload replaces manual rows only (approved extracted memory kept).
        db.query(Claim).filter(
            Claim.scene_id == scene.id,
            Claim.source == "manual",
        ).delete(synchronize_session=False)
        for c in manual_claims:
            if not c.subject.strip() or not c.predicate.strip() or not c.object.strip():
                continue
            db.add(_manual_claim_row(scene.story_id, scene.id, c))

    db.flush()

    extraction_out: SceneExtractionOut | None = None
    if run_extraction and scene.text.strip():
        delete_replaceable_scene_claims(db, scene)
        result = extract_claims_from_text(
            scene.text, pov_character=scene.pov_character
        )
        merge_extracted_claims_for_scene(db, scene, result.claims)
        all_rows = (
            db.query(Claim).filter(Claim.scene_id == scene.id).order_by(Claim.id).all()
        )
        extraction_out = _extraction_summary(result, all_rows)
    else:
        all_rows = (
            db.query(Claim).filter(Claim.scene_id == scene.id).order_by(Claim.id).all()
        )

    validate_scene_claims(db, scene, all_rows)
    return all_rows, extraction_out
