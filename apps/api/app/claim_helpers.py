import json

from app.models import Claim
from app.schemas import ClaimOut


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


def claim_to_out(c: Claim) -> ClaimOut:
    return ClaimOut(
        id=c.id,
        subject=c.subject,
        predicate=c.predicate,
        object=c.claim_object,
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
        chunk_index=c.chunk_index,
        claim_version=c.claim_version,
        superseded_by_claim_id=c.superseded_by_claim_id,
        source_hash=c.source_hash,
    )
