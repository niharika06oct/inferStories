"""Save chapters and run automatic claim extraction."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extraction import extract_claims_from_text
from app.extraction.merge import MergeStats
from app.extraction.persist import (
    delete_replaceable_scene_claims,
    merge_extracted_claims_for_scene,
    remove_stale_scene_claims,
)
from app.extraction.schema import ExtractionResult
from app.claim_entities import resolve_manual
from app.entity_registry import ensure_pov_entity, is_placeholder_entity_name
from app.models import Claim, Scene, ValidationIssue
from app.schemas import ClaimIn, SceneExtractionOut
from app.nlp.fastus_debug import lifecycle_dict_to_out, log_stage, log_stage_dict
from app.validation import ValidationStats, validate_scene_claims


def _manual_claim_row(
    db: Session, story_id: int, scene_id: int, c: ClaimIn
) -> Claim:
    resolved = resolve_manual(
        db,
        story_id,
        subject=c.subject,
        predicate=c.predicate,
        claim_object=c.object,
        claim_type=c.claim_type,
        claim_text=c.claim_text,
        polarity=c.polarity,
    )
    now = datetime.utcnow()
    return Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=resolved.subject,
        predicate=resolved.predicate,
        claim_object=resolved.claim_object,
        polarity=resolved.polarity,
        subject_entity_id=resolved.subject_entity_id,
        object_entity_id=resolved.object_entity_id,
        claim_type=resolved.claim_type,
        claim_text=c.claim_text
        or f"{resolved.subject} {resolved.predicate} {resolved.claim_object}".strip(),
        confidence=c.confidence if c.confidence is not None else 1.0,
        canon_level=c.canon_level or "active",
        status="approved",
        evidence_text=c.evidence_text,
        source="manual",
        generation_origin="manual",
        created_at=now,
        updated_at=now,
        extracted_at=None,
        is_major_plotline=c.is_major_plotline,
        source_hash=resolved.source_hash,
        claim_version=1,
    )


def _extraction_summary(
    result: ExtractionResult,
    rows: list[Claim],
    *,
    merge_stats: MergeStats | None = None,
) -> SceneExtractionOut:
    needs_review = sum(1 for r in rows if r.status == "needs_review")
    suggested = sum(1 for r in rows if r.status == "suggested")
    approved = sum(1 for r in rows if r.status == "approved")
    from app.schemas import ChunkExtractionDebugOut, FastusDebugEventOut

    gen_counts: dict[str, int] = {}
    for r in rows:
        key = (r.generation_origin or "unknown").strip() or "unknown"
        gen_counts[key] = gen_counts.get(key, 0) + 1

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
        suppressed_structural_count=result.suppressed_structural_count,
        generation_counts=gen_counts,
        fastus_spacy_available=result.fastus_spacy_available,
        fastus_stage0_negated_claims=result.fastus_stage0_negated_claims,
        fastus_stage0_rejected_fragments=result.fastus_stage0_rejected_fragments,
        fastus_events=[
            FastusDebugEventOut(**e.model_dump()) for e in result.fastus_events
        ]
        + [
            FastusDebugEventOut(
                stage=ev["stage"],
                event=ev["event"],
                message=ev["message"],
                detail=ev.get("detail") or {},
            )
            for ev in (merge_stats.events if merge_stats else [])
        ],
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
                fastus_token_count=c.fastus_token_count,
                fastus_sentence_count=c.fastus_sentence_count,
                fastus_has_dependencies=c.fastus_has_dependencies,
                fastus_entity_candidate_count=c.fastus_entity_candidate_count,
                fastus_phrase_candidate_count=c.fastus_phrase_candidate_count,
                fastus_events=[
                    FastusDebugEventOut(**e.model_dump()) for e in c.fastus_events
                ],
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

    Re-extraction deletes only suggested / needs_review / deprecated rows,
    then merges new extractions (updates approved and rejected matches in place).
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
            if is_placeholder_entity_name(c.subject) or is_placeholder_entity_name(
                c.object
            ):
                # "I"/"Narrator" cannot be a canonical subject/object; needs a real name.
                continue
            db.add(_manual_claim_row(db, scene.story_id, scene.id, c))

    db.flush()

    extraction_out: SceneExtractionOut | None = None
    touched_ids: set[int] = set()
    post_save_events: list[dict[str, str]] = []
    merge_stats: MergeStats | None = None
    stale_removed = 0

    if run_extraction and scene.text.strip():
        log_stage_dict(
            post_save_events,
            stage="7",
            lifecycle="begin",
            message="Merging extracted claims into story memory",
        )
        ensure_pov_entity(db, scene.story_id, scene.pov_character)
        delete_replaceable_scene_claims(db, scene)
        result = extract_claims_from_text(
            scene.text, pov_character=scene.pov_character
        )
        merge_stats = MergeStats()
        touched = merge_extracted_claims_for_scene(
            db, scene, result.claims, merge_stats=merge_stats
        )
        touched_ids = {row.id for row in touched if row.id is not None}
        all_rows = (
            db.query(Claim).filter(Claim.scene_id == scene.id).order_by(Claim.id).all()
        )
        extraction_out = _extraction_summary(
            result, all_rows, merge_stats=merge_stats
        )
    else:
        reason = (
            "run_extraction=false (autosave text-only)"
            if not run_extraction
            else "empty chapter text"
        )
        log_stage_dict(
            post_save_events,
            stage="7",
            lifecycle="skip",
            message=f"Merge skipped — {reason}",
        )
        all_rows = (
            db.query(Claim).filter(Claim.scene_id == scene.id).order_by(Claim.id).all()
        )

    if scene.text.strip():
        stale_removed = len(
            remove_stale_scene_claims(db, scene, touched_ids=touched_ids)
        )
        db.flush()
        all_rows = (
            db.query(Claim).filter(Claim.scene_id == scene.id).order_by(Claim.id).all()
        )
        if merge_stats is not None:
            log_stage_dict(
                post_save_events,
                stage="7",
                lifecycle="complete",
                message="Merge and prune finished",
                detail={
                    "inserted": str(merge_stats.inserted),
                    "updated": str(merge_stats.updated),
                    "transitions": str(merge_stats.transitions),
                    "stale_removed": str(stale_removed),
                    "claims_on_scene": str(len(all_rows)),
                },
            )
        elif stale_removed:
            log_stage_dict(
                post_save_events,
                stage="7",
                lifecycle="complete",
                message="Stale prune finished (merge was skipped)",
                detail={
                    "stale_removed": str(stale_removed),
                    "claims_on_scene": str(len(all_rows)),
                },
            )
        else:
            log_stage_dict(
                post_save_events,
                stage="7",
                lifecycle="complete",
                message="No stale claims removed",
                detail={"claims_on_scene": str(len(all_rows))},
            )
    elif merge_stats is not None:
        log_stage_dict(
            post_save_events,
            stage="7",
            lifecycle="complete",
            message="Merge finished (no text for stale prune)",
            detail={
                "inserted": str(merge_stats.inserted),
                "updated": str(merge_stats.updated),
                "transitions": str(merge_stats.transitions),
            },
        )

    validation_stats = ValidationStats()
    log_stage_dict(
        post_save_events,
        stage="8",
        lifecycle="begin",
        message="Running continuity validation",
        detail={"claims_checked": str(len(all_rows))},
    )
    validate_scene_claims(db, scene, all_rows, validation_stats=validation_stats)
    log_stage_dict(
        post_save_events,
        stage="8",
        lifecycle="complete",
        message="Continuity validation finished",
        detail={
            "issues_raised": str(validation_stats.issues_raised),
            "superseded_skipped": str(validation_stats.superseded_skipped),
            "polarity_flips": str(validation_stats.polarity_flips),
        },
    )
    if validation_stats.issues_raised > 0:
        log_stage_dict(
            post_save_events,
            stage="9",
            lifecycle="complete",
            message="Enriched continuity issues with evidence and suggested fixes",
            detail={"issues_enriched": str(validation_stats.issues_raised)},
        )
    else:
        log_stage_dict(
            post_save_events,
            stage="9",
            lifecycle="skip",
            message="No continuity issues to enrich",
        )
    if extraction_out is not None:
        from app.schemas import FastusDebugEventOut

        extraction_out.fastus_events.extend(lifecycle_dict_to_out(post_save_events))
        extraction_out.fastus_events.extend(
            FastusDebugEventOut(
                stage=ev["stage"],
                event=ev["event"],
                message=ev["message"],
                detail=ev.get("detail") or {},
            )
            for ev in (merge_stats.events if merge_stats else [])
        )
        extraction_out.fastus_events.extend(
            FastusDebugEventOut(
                stage=ev["stage"],
                event=ev["event"],
                message=ev["message"],
                detail=ev.get("detail") or {},
            )
            for ev in validation_stats.events
        )
    else:
        log_stage(
            None,
            stage="meta",
            lifecycle="warn",
            message="Stages 7–9 ran without extraction summary (text-only save path)",
            detail={"post_save_events": len(post_save_events)},
        )
    return all_rows, extraction_out
