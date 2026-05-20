from app.models import Claim
from app.schemas import ClaimOut


def claim_to_out(c: Claim) -> ClaimOut:
    return ClaimOut(
        id=c.id,
        subject=c.subject,
        predicate=c.predicate,
        object=c.claim_object,
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
    )
