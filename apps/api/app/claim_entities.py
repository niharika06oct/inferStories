"""Resolve extracted or manual claim strings to canonical story entities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.claim_identity import compute_entity_source_hash, source_hash_for_claim_row
from app.entity_registry import (
    _CLAIM_TYPE_SLUGS,
    get_or_create_entity,
    guess_entity_type,
    infer_predicate_from_claim,
)
from app.extraction.schema import ExtractedClaim
from app.models import Claim


@dataclass(frozen=True)
class ResolvedClaimFields:
    subject: str
    predicate: str
    claim_object: str
    claim_type: str
    subject_entity_id: int
    object_entity_id: int | None
    source_hash: str


def resolve_extracted(
    db: Session, story_id: int, extracted: ExtractedClaim
) -> ResolvedClaimFields:
    target = (extracted.target or "").strip()
    claim_type = extracted.claim_type.strip()
    predicate = infer_predicate_from_claim(
        claim_type,
        extracted.claim,
        extracted.predicate,
    )

    subj_type = guess_entity_type(extracted.subject.strip(), claim_type)
    subj_ent = get_or_create_entity(
        db, story_id, extracted.subject.strip(), subj_type
    )
    obj_ent = None
    if target:
        obj_type = guess_entity_type(target, claim_type)
        obj_ent = get_or_create_entity(db, story_id, target, obj_type)

    claim_object = target or extracted.claim[:255]
    source_hash = compute_entity_source_hash(
        subj_ent.id,
        predicate,
        obj_ent.id if obj_ent else None,
        claim_type,
    )
    return ResolvedClaimFields(
        subject=subj_ent.canonical_name,
        predicate=predicate,
        claim_object=obj_ent.canonical_name if obj_ent else claim_object,
        claim_type=claim_type,
        subject_entity_id=subj_ent.id,
        object_entity_id=obj_ent.id if obj_ent else None,
        source_hash=source_hash,
    )


def resolve_manual(
    db: Session,
    story_id: int,
    *,
    subject: str,
    predicate: str,
    claim_object: str,
    claim_type: str | None,
    claim_text: str | None,
) -> ResolvedClaimFields:
    ct = (claim_type or "relationship_state").strip()
    pred = predicate.strip()
    if pred.lower() in _CLAIM_TYPE_SLUGS:
        pred = infer_predicate_from_claim(ct, claim_text or f"{subject} {pred} {claim_object}")

    subj_ent = get_or_create_entity(
        db, story_id, subject.strip(), guess_entity_type(subject, ct)
    )
    obj_ent = None
    if claim_object.strip():
        obj_ent = get_or_create_entity(
            db,
            story_id,
            claim_object.strip(),
            guess_entity_type(claim_object, ct),
        )

    source_hash = compute_entity_source_hash(
        subj_ent.id,
        pred,
        obj_ent.id if obj_ent else None,
        ct,
    )
    return ResolvedClaimFields(
        subject=subj_ent.canonical_name,
        predicate=pred,
        claim_object=obj_ent.canonical_name if obj_ent else claim_object.strip(),
        claim_type=ct,
        subject_entity_id=subj_ent.id,
        object_entity_id=obj_ent.id if obj_ent else None,
        source_hash=source_hash,
    )


def rehash_claim_row(claim: Claim) -> str:
    if claim.subject_entity_id:
        return compute_entity_source_hash(
            claim.subject_entity_id,
            claim.predicate,
            claim.object_entity_id,
            claim.claim_type or "",
        )
    return source_hash_for_claim_row(
        claim.subject,
        claim.predicate,
        claim.claim_object,
        claim.claim_type,
    )
