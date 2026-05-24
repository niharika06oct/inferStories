"""Persist extracted claims with confidence-based lifecycle and merge on re-analyze."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.claim_entities import resolve_extracted, rehash_claim_row
from app.claim_identity import PRESERVED_STATUSES, REPLACABLE_STATUSES
from app.extraction.extract import status_for_confidence
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene


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
    row.source_hash = resolved.source_hash
    row.is_major_plotline = (
        extracted.claim_type == "plotline_fact" or extracted.canon_level == "core"
    )
    if not preserve_status:
        row.status = status_for_confidence(extracted.confidence)


def delete_replaceable_scene_claims(db: Session, scene: Scene) -> int:
    """Remove non-canon claims before re-extraction (keeps approved / canonized)."""
    return (
        db.query(Claim)
        .filter(
            Claim.scene_id == scene.id,
            Claim.status.in_(REPLACABLE_STATUSES),
        )
        .delete(synchronize_session=False)
    )


def _preserved_by_hash(db: Session, scene: Scene) -> dict[str, Claim]:
    rows = (
        db.query(Claim)
        .filter(
            Claim.scene_id == scene.id,
            Claim.status.in_(PRESERVED_STATUSES),
        )
        .all()
    )
    out: dict[str, Claim] = {}
    for row in rows:
        h = row.source_hash or rehash_claim_row(row)
        row.source_hash = h
        out[h] = row
    return out


def merge_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    """
    Upsert extracted claims by source_hash (entity-aware).

    - Approved/canonized rows with the same hash are updated in place (version++).
    - New hashes insert new rows.
    - Approved claims not present in this extraction pass are left unchanged.
    """
    preserved = _preserved_by_hash(db, scene)
    touched: list[Claim] = []
    version_bumped: set[str] = set()

    for item in extracted_claims:
        resolved = resolve_extracted(db, scene.story_id, item)
        h = resolved.source_hash
        existing = preserved.get(h)
        if existing is not None:
            _apply_extraction_to_row(
                existing, item, resolved=resolved, preserve_status=True
            )
            if h not in version_bumped:
                existing.claim_version = (existing.claim_version or 1) + 1
                version_bumped.add(h)
            touched.append(existing)
            continue

        row = _claim_to_row(scene.story_id, scene.id, item, resolved=resolved)
        db.add(row)
        touched.append(row)
        preserved[h] = row

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
