"""Persist extracted claims with confidence-based lifecycle and merge on re-analyze."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.claim_entities import resolve_extracted, rehash_claim_row
from app.claim_identity import (
    MERGE_PRESERVE_STATUSES,
    PRESERVED_STATUSES,
    REPLACABLE_STATUSES,
    norm_evidence,
    predicate_merge_key,
)
from app.extraction.extract import resolve_extracted_status
from app.extraction.merge import (
    MergeStats,
    append_confidence_history,
    entity_pair_merge_key,
    find_open_transition_prior,
    init_confidence_history,
    record_merge_event,
    register_subject_predicate_index,
)
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene, ValidationIssue
from app.validation_evidence import claim_anchored_in_scene


def _utc_now() -> datetime:
    return datetime.utcnow()


def _claim_to_row(
    story_id: int,
    scene_id: int,
    extracted: ExtractedClaim,
    *,
    resolved,
    valid_from_scene: int | None = None,
) -> Claim:
    status = resolve_extracted_status(extracted)
    is_plotline = extracted.claim_type == "plotline_fact"
    now = _utc_now()
    row = Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=resolved.subject,
        predicate=resolved.predicate,
        claim_object=resolved.claim_object,
        polarity=resolved.polarity,
        subject_entity_id=resolved.subject_entity_id,
        object_entity_id=resolved.object_entity_id,
        claim_type=resolved.claim_type,
        claim_text=extracted.claim.strip(),
        confidence=extracted.confidence,
        canon_level=extracted.canon_level,
        status=status,
        evidence_text=extracted.evidence.strip(),
        chunk_index=extracted.chunk_index,
        source="extracted",
        generation_origin=extracted.generation_origin,
        created_at=now,
        updated_at=now,
        extracted_at=now,
        is_major_plotline=is_plotline or extracted.canon_level == "core",
        source_hash=resolved.source_hash,
        claim_version=1,
        valid_from_scene=valid_from_scene or scene_id,
        valid_until_scene=None,
    )
    init_confidence_history(
        row, confidence=extracted.confidence, scene_id=scene_id
    )
    return row


def _apply_extraction_to_row(
    row: Claim,
    extracted: ExtractedClaim,
    *,
    resolved,
    preserve_status: bool,
    scene_id: int,
) -> None:
    row.subject = resolved.subject
    row.predicate = resolved.predicate
    row.claim_object = resolved.claim_object
    row.polarity = resolved.polarity
    row.subject_entity_id = resolved.subject_entity_id
    row.object_entity_id = resolved.object_entity_id
    row.claim_type = resolved.claim_type
    row.claim_text = extracted.claim.strip()
    row.confidence = extracted.confidence
    row.canon_level = extracted.canon_level
    row.evidence_text = extracted.evidence.strip()
    row.chunk_index = extracted.chunk_index
    row.generation_origin = extracted.generation_origin
    row.extracted_at = _utc_now()
    row.updated_at = _utc_now()
    row.source_hash = resolved.source_hash
    row.is_major_plotline = (
        extracted.claim_type == "plotline_fact" or extracted.canon_level == "core"
    )
    if not preserve_status:
        row.status = status_for_confidence(extracted.confidence)


def remove_stale_scene_claims(
    db: Session,
    scene: Scene,
    *,
    touched_ids: set[int] | None = None,
) -> list[int]:
    """
    Drop scene claims whose evidence no longer appears in the chapter text.

    Preserves rows refreshed by the current extraction pass (touched_ids) and
    manual author-entered claims (source=manual).
    """
    touched = touched_ids or set()
    to_remove: list[Claim] = []
    rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
    for row in rows:
        if row.id is not None and row.id in touched:
            continue
        if (row.source or "").strip() == "manual":
            continue
        if claim_anchored_in_scene(scene.text or "", row):
            continue
        to_remove.append(row)

    removed_ids = [row.id for row in to_remove if row.id is not None]
    if removed_ids:
        db.query(ValidationIssue).filter(
            ValidationIssue.story_id == scene.story_id,
            or_(
                ValidationIssue.current_claim_id.in_(removed_ids),
                ValidationIssue.conflicting_claim_id.in_(removed_ids),
            ),
        ).delete(synchronize_session=False)
    for row in to_remove:
        db.delete(row)
    return removed_ids


def delete_replaceable_scene_claims(db: Session, scene: Scene) -> int:
    """Remove tentative claims before re-extraction (keeps approved / rejected / canonized)."""
    return (
        db.query(Claim)
        .filter(
            Claim.scene_id == scene.id,
            Claim.status.in_(REPLACABLE_STATUSES),
        )
        .delete(synchronize_session=False)
    )


def _preserved_indexes(
    db: Session, scene: Scene
) -> tuple[
    dict[str, Claim],
    list[Claim],
    dict[str, Claim],
    dict[tuple, Claim],
    dict[tuple, Claim],
]:
    rows = (
        db.query(Claim)
        .filter(
            Claim.scene_id == scene.id,
            Claim.status.in_(MERGE_PRESERVE_STATUSES),
        )
        .all()
    )
    by_hash: dict[str, Claim] = {}
    by_evidence: dict[str, Claim] = {}
    by_entity_pair: dict[tuple, Claim] = {}
    by_subject_predicate: dict[tuple, Claim] = {}
    for row in rows:
        h = row.source_hash or rehash_claim_row(row)
        row.source_hash = h
        by_hash[h] = row
        ev = norm_evidence(row.evidence_text or "")
        if ev and ev not in by_evidence:
            by_evidence[ev] = row
        polarity = getattr(row, "polarity", True)
        if row.subject_entity_id and row.object_entity_id:
            pair = entity_pair_merge_key(
                row.subject_entity_id,
                row.object_entity_id,
                row.predicate or "",
                polarity=polarity,
            )
            if pair not in by_entity_pair:
                by_entity_pair[pair] = row
        register_subject_predicate_index(by_subject_predicate, row)
    return by_hash, rows, by_evidence, by_entity_pair, by_subject_predicate


def _story_canon_indexes(
    db: Session,
    story_id: int,
) -> tuple[dict[str, Claim], dict[tuple, Claim]]:
    """Approved/canonized open facts anywhere in the story (cross-chapter memory)."""
    rows = (
        db.query(Claim)
        .filter(
            Claim.story_id == story_id,
            Claim.status.in_(PRESERVED_STATUSES),
        )
        .all()
    )
    by_hash: dict[str, Claim] = {}
    by_entity_pair: dict[tuple, Claim] = {}
    for row in rows:
        if getattr(row, "valid_until_scene", None) is not None:
            continue
        h = row.source_hash or rehash_claim_row(row)
        if h and h not in by_hash:
            by_hash[h] = row
        polarity = getattr(row, "polarity", True)
        if row.subject_entity_id and row.object_entity_id:
            pair = entity_pair_merge_key(
                row.subject_entity_id,
                row.object_entity_id,
                row.predicate or "",
                polarity=polarity,
            )
            if pair not in by_entity_pair:
                by_entity_pair[pair] = row
    return by_hash, by_entity_pair


def _find_story_canon_match(
    *,
    by_hash: dict[str, Claim],
    by_entity_pair: dict[tuple, Claim],
    source_hash: str,
    subject_entity_id: int,
    object_entity_id: int | None,
    predicate: str,
    polarity: bool,
) -> Claim | None:
    """Match extracted fact against accepted memory from any earlier chapter."""
    if source_hash in by_hash:
        return by_hash[source_hash]
    if subject_entity_id and object_entity_id:
        pair = entity_pair_merge_key(
            subject_entity_id,
            object_entity_id,
            predicate,
            polarity=polarity,
        )
        if pair in by_entity_pair:
            return by_entity_pair[pair]
    return None


def _find_preserved_match(
    *,
    by_hash: dict[str, Claim],
    by_evidence: dict[str, Claim],
    by_entity_pair: dict[tuple, Claim],
    source_hash: str,
    evidence: str,
    subject_entity_id: int,
    object_entity_id: int | None,
    predicate: str,
    polarity: bool,
) -> Claim | None:
    if source_hash in by_hash:
        return by_hash[source_hash]

    ev = norm_evidence(evidence)
    if ev and ev in by_evidence:
        candidate = by_evidence[ev]
        if getattr(candidate, "polarity", True) == polarity:
            return candidate

    if subject_entity_id and object_entity_id:
        pair = entity_pair_merge_key(
            subject_entity_id,
            object_entity_id,
            predicate,
            polarity=polarity,
        )
        if pair in by_entity_pair:
            return by_entity_pair[pair]

    return None


def _index_row(
    row: Claim,
    *,
    by_hash: dict[str, Claim],
    by_evidence: dict[str, Claim],
    by_entity_pair: dict[tuple, Claim],
    by_subject_predicate: dict[tuple, Claim],
    evidence: str,
    resolved,
) -> None:
    h = row.source_hash or ""
    if h:
        by_hash[h] = row
    ev = norm_evidence(evidence)
    if ev:
        by_evidence[ev] = row
    if resolved.object_entity_id:
        pair = entity_pair_merge_key(
            resolved.subject_entity_id,
            resolved.object_entity_id,
            resolved.predicate,
            polarity=resolved.polarity,
        )
        by_entity_pair[pair] = row
    register_subject_predicate_index(by_subject_predicate, row)


def merge_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
    *,
    merge_stats: MergeStats | None = None,
) -> list[Claim]:
    """
    Upsert extracted claims by polarity-aware source_hash (entity-aware).

    - Same subject, predicate, object, polarity: reinforcement (version++).
    - Opposite polarity: distinct identity (separate rows via source_hash).
    - Same subject, predicate, polarity, different object: state transition
      (valid_until on prior, valid_from on new) for relational predicates.
    """
    (
        by_hash,
        _,
        by_evidence,
        by_entity_pair,
        by_subject_predicate,
    ) = _preserved_indexes(db, scene)
    story_canon_hash, story_canon_pair = _story_canon_indexes(db, scene.story_id)
    touched: list[Claim] = []
    version_bumped: set[int] = set()

    for item in extracted_claims:
        resolved = resolve_extracted(db, scene.story_id, item)
        h = resolved.source_hash
        existing = _find_preserved_match(
            by_hash=by_hash,
            by_evidence=by_evidence,
            by_entity_pair=by_entity_pair,
            source_hash=h,
            evidence=item.evidence,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            predicate=resolved.predicate,
            polarity=resolved.polarity,
        )
        if existing is not None:
            _apply_extraction_to_row(
                existing,
                item,
                resolved=resolved,
                preserve_status=True,
                scene_id=scene.id,
            )
            old_hash = existing.source_hash
            if old_hash and old_hash in by_hash and by_hash[old_hash] is existing:
                del by_hash[old_hash]
            existing.source_hash = h
            if existing.id not in version_bumped:
                existing.claim_version = (existing.claim_version or 1) + 1
                version_bumped.add(existing.id)
                append_confidence_history(
                    existing,
                    confidence=item.confidence,
                    scene_id=scene.id,
                    version=existing.claim_version,
                )
            _index_row(
                existing,
                by_hash=by_hash,
                by_evidence=by_evidence,
                by_entity_pair=by_entity_pair,
                by_subject_predicate=by_subject_predicate,
                evidence=item.evidence,
                resolved=resolved,
            )
            touched.append(existing)
            if merge_stats is not None:
                merge_stats.updated += 1
            record_merge_event(
                merge_stats,
                event="merge_reinforce",
                message=(
                    f"Reinforced {resolved.subject} {resolved.predicate} "
                    f"{resolved.claim_object} (v{existing.claim_version})"
                ),
                detail={
                    "polarity": "true" if resolved.polarity else "false",
                    "source_hash": h,
                },
            )
            continue

        prior = find_open_transition_prior(
            by_subject_predicate,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            predicate=resolved.predicate,
            polarity=resolved.polarity,
        )
        valid_from = scene.id
        if prior is not None:
            prior.valid_until_scene = scene.id
            register_subject_predicate_index(by_subject_predicate, prior)
            if merge_stats is not None:
                merge_stats.transitions += 1
            record_merge_event(
                merge_stats,
                event="state_transition",
                message=(
                    f"Closed {prior.subject} {prior.predicate} {prior.claim_object} "
                    f"→ opened {resolved.claim_object}"
                ),
                detail={
                    "prior_id": str(prior.id),
                    "polarity": "true" if resolved.polarity else "false",
                },
            )

        canon_prior = _find_story_canon_match(
            by_hash=story_canon_hash,
            by_entity_pair=story_canon_pair,
            source_hash=h,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            predicate=resolved.predicate,
            polarity=resolved.polarity,
        )
        if canon_prior is not None:
            if merge_stats is not None:
                merge_stats.updated += 1
            record_merge_event(
                merge_stats,
                event="canon_suppress",
                message=(
                    f"Skipped {resolved.subject} {resolved.predicate} "
                    f"{resolved.claim_object} — already accepted in story memory"
                ),
                detail={
                    "polarity": "true" if resolved.polarity else "false",
                    "prior_scene_id": str(canon_prior.scene_id),
                    "prior_claim_id": str(canon_prior.id),
                    "source_hash": h,
                },
            )
            continue

        row = _claim_to_row(
            scene.story_id,
            scene.id,
            item,
            resolved=resolved,
            valid_from_scene=valid_from,
        )
        db.add(row)
        touched.append(row)
        _index_row(
            row,
            by_hash=by_hash,
            by_evidence=by_evidence,
            by_entity_pair=by_entity_pair,
            by_subject_predicate=by_subject_predicate,
            evidence=item.evidence,
            resolved=resolved,
        )
        if merge_stats is not None:
            merge_stats.inserted += 1
        record_merge_event(
            merge_stats,
            event="merge_insert",
            message=(
                f"Inserted {resolved.subject} {resolved.predicate} "
                f"{resolved.claim_object}"
            ),
            detail={
                "polarity": "true" if resolved.polarity else "false",
                "source_hash": h,
            },
        )

    db.flush()
    return touched


def replace_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
    *,
    merge_stats: MergeStats | None = None,
) -> list[Claim]:
    """Legacy name — callers should prefer merge after delete_replaceable_scene_claims."""
    delete_replaceable_scene_claims(db, scene)
    return merge_extracted_claims_for_scene(
        db, scene, extracted_claims, merge_stats=merge_stats
    )


def persist_extracted_claims(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
    *,
    merge_stats: MergeStats | None = None,
) -> list[Claim]:
    delete_replaceable_scene_claims(db, scene)
    return merge_extracted_claims_for_scene(
        db, scene, extracted_claims, merge_stats=merge_stats
    )
