"""Persist extracted claims with confidence-based lifecycle."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.extraction.extract import status_for_confidence
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene


def _claim_to_row(
    story_id: int,
    scene_id: int,
    extracted: ExtractedClaim,
) -> Claim:
    status = status_for_confidence(extracted.confidence)
    target = (extracted.target or "").strip()
    is_plotline = extracted.claim_type == "plotline_fact"
    return Claim(
        story_id=story_id,
        scene_id=scene_id,
        subject=extracted.subject.strip(),
        predicate=extracted.claim_type,
        claim_object=target or extracted.claim[:255],
        claim_type=extracted.claim_type,
        claim_text=extracted.claim.strip(),
        confidence=extracted.confidence,
        canon_level=extracted.canon_level,
        status=status,
        evidence_text=extracted.evidence.strip(),
        chunk_index=extracted.chunk_index,
        source="extracted",
        is_major_plotline=is_plotline
        or extracted.canon_level == "core",
    )


def replace_extracted_claims_for_scene(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    db.query(Claim).filter(
        Claim.scene_id == scene.id,
        Claim.source == "extracted",
    ).delete(synchronize_session=False)

    rows: list[Claim] = []
    for item in extracted_claims:
        row = _claim_to_row(scene.story_id, scene.id, item)
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def persist_extracted_claims(
    db: Session,
    scene: Scene,
    extracted_claims: list[ExtractedClaim],
) -> list[Claim]:
    return replace_extracted_claims_for_scene(db, scene, extracted_claims)
