import json

from app.models import Claim
from app.schemas import ClaimOut
from app.validation_evidence import claim_anchored_in_scene, locate_claim_evidence_span


def _aliases_for_out(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(a) for a in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def claim_to_out(c: Claim, *, scene_text: str | None = None) -> ClaimOut:
    evidence_anchored = (
        claim_anchored_in_scene(scene_text, c) if scene_text else None
    )
    evidence_offset: int | None = None
    evidence_length: int | None = None
    if scene_text:
        off, length, _anchor = locate_claim_evidence_span(
            scene_text,
            evidence_text=c.evidence_text,
            claim_text=c.claim_text,
            claim_object=c.claim_object,
            claim_subject=c.subject,
        )
        if off >= 0 and length > 0:
            evidence_offset = off
            evidence_length = length
    return ClaimOut(
        id=c.id,
        subject=c.subject,
        predicate=c.predicate,
        object=c.claim_object,
        polarity=getattr(c, "polarity", True),
        subject_entity_id=c.subject_entity_id,
        object_entity_id=c.object_entity_id,
        is_major_plotline=c.is_major_plotline,
        claim_type=c.claim_type or c.predicate,
        claim_text=c.claim_text,
        target=c.claim_object if c.claim_type in (
            "relationship_state",
            "relationship_change",
        ) else (c.claim_object or None),
        confidence=c.confidence,
        canon_level=c.canon_level,
        status=c.status,
        evidence_text=c.evidence_text,
        source=c.source,
        generation_origin=c.generation_origin,
        created_at=c.created_at,
        updated_at=c.updated_at,
        extracted_at=c.extracted_at,
        chunk_index=c.chunk_index,
        claim_version=c.claim_version,
        superseded_by_claim_id=c.superseded_by_claim_id,
        source_hash=c.source_hash,
        valid_from_scene=getattr(c, "valid_from_scene", None),
        valid_until_scene=getattr(c, "valid_until_scene", None),
        confidence_history=getattr(c, "confidence_history", None),
        evidence_anchored=evidence_anchored,
        evidence_offset=evidence_offset,
        evidence_length=evidence_length,
    )
