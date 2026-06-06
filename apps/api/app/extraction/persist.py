"""Persist extracted claims with confidence-based lifecycle and merge on re-analyze."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.claim_entities import resolve_extracted, rehash_claim_row
from app.claim_identity import (
    MERGE_PRESERVE_STATUSES,
    REPLACABLE_STATUSES,
    norm_evidence,
    predicate_merge_key,
)
from app.extraction.extract import status_for_confidence
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene


def _utc_now() -> datetime:
    return datetime.utcnow()


def _claim_to_row(
    story_id: int,
    scene_id: int,
    extracted: ExtractedClaim,
    *,
    resolved,
) -> Claim:
    status = status_for_confidence(extracted.confidence)
    target = (extracted.target or "").strip()
    is_plotline = extracted.claim_type == "plotline_fact"
    now = _utc_now()
    return Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=resolved.subject,
        predicate=resolved.predicate,
        claim_object=resolved.claim_object,
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
    )


def _apply_extraction_to_row(
    row: Claim,
    extracted: ExtractedClaim,
    *,
    resolved,
    preserve_status: bool,
) -> None:
    row.subject = resolved.subject
    row.predicate = resolved.predicate
    row.claim_object = resolved.claim_object
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
) -> tuple[dict[str, Claim], list[Claim], dict[str, Claim], dict[tuple, Claim]]:
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
    for row in rows:
        h = row.source_hash or rehash_claim_row(row)
        row.source_hash = h
        by_hash[h] = row
        ev = norm_evidence(row.evidence_text or "")
        if ev and ev not in by_evidence:
            by_evidence[ev] = row
        if row.subject_entity_id and row.object_entity_id:
            pair = (
                row.subject_entity_id,
                row.object_entity_id,
                predicate_merge_key(row.predicate or ""),
            )
            if pair not in by_entity_pair:
                by_entity_pair[pair] = row
    return by_hash, rows, by_evidence, by_entity_pair


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
) -> Claim | None:
    if source_hash in by_hash:
        return by_hash[source_hash]

    ev = norm_evidence(evidence)
    if ev and ev in by_evidence:
        return by_evidence[ev]

    if subject_entity_id and object_entity_id:
        pair = (
            subject_entity_id,
            object_entity_id,
            predicate_merge_key(predicate),
        )
        if pair in by_entity_pair:
            return by_entity_pair[pair]

    return None


def merge_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    """
    Upsert extracted claims by source_hash (entity-aware).

    - Approved/canonized/rejected rows matching hash, evidence, or entity pair are
      updated in place (version++) without changing status.
    - New hashes insert new suggested rows.
    - Preserved claims not present in this extraction pass are left unchanged.
    """
    by_hash, _, by_evidence, by_entity_pair = _preserved_indexes(db, scene)
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
        )
        if existing is not None:
            _apply_extraction_to_row(
                existing, item, resolved=resolved, preserve_status=True
            )
            old_hash = existing.source_hash
            if old_hash and old_hash in by_hash and by_hash[old_hash] is existing:
                del by_hash[old_hash]
            existing.source_hash = h
            by_hash[h] = existing
            ev = norm_evidence(item.evidence)
            if ev:
                by_evidence[ev] = existing
            if resolved.object_entity_id:
                pair = (
                    resolved.subject_entity_id,
                    resolved.object_entity_id,
                    predicate_merge_key(resolved.predicate),
                )
                by_entity_pair[pair] = existing
            if existing.id not in version_bumped:
                existing.claim_version = (existing.claim_version or 1) + 1
                version_bumped.add(existing.id)
            touched.append(existing)
            continue

        row = _claim_to_row(scene.story_id, scene.id, item, resolved=resolved)
        db.add(row)
        touched.append(row)
        by_hash[h] = row
        ev = norm_evidence(item.evidence)
        if ev:
            by_evidence[ev] = row
        if resolved.object_entity_id:
            pair = (
                resolved.subject_entity_id,
                resolved.object_entity_id,
                predicate_merge_key(resolved.predicate),
            )
            by_entity_pair[pair] = row

    db.flush()
    return touched


def replace_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    """Legacy name — callers should prefer merge after delete_replaceable_scene_claims."""
    delete_replaceable_scene_claims(db, scene)
    return merge_extracted_claims_for_scene(db, scene, extracted_claims)


def persist_extracted_claims(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    delete_replaceable_scene_claims(db, scene)
    return merge_extracted_claims_for_scene(db, scene, extracted_claims)
