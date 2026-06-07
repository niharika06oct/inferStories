"""Resolve extracted or manual claim strings to canonical story entities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.claim_identity import compute_entity_source_hash, source_hash_for_claim_row
from app.entity_classification import classify_entity_surface, refine_claim_type
from app.entity_registry import (
    _CLAIM_TYPE_SLUGS,
    get_or_create_entity,
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
    polarity: bool = True


def resolve_extracted(
    db: Session, story_id: int, extracted: ExtractedClaim
) -> ResolvedClaimFields:
    target = (extracted.target or "").strip()
    context = extracted.claim.strip()
    evidence = extracted.evidence.strip()

    predicate = infer_predicate_from_claim(
        extracted.claim_type,
        context,
        extracted.predicate,
    )

    subj_type, _ = classify_entity_surface(
        extracted.subject.strip(),
        sentence=context,
        evidence=evidence,
        role="subject",
    )
    subj_ent = get_or_create_entity(
        db,
        story_id,
        extracted.subject.strip(),
        subj_type,
        sentence=context,
        evidence=evidence,
        role="subject",
    )

    obj_ent = None
    obj_type = None
    if target:
        obj_type, _ = classify_entity_surface(
            target,
            sentence=context,
            evidence=evidence,
            role="object",
        )
        obj_ent = get_or_create_entity(
            db,
            story_id,
            target,
            obj_type,
            sentence=context,
            evidence=evidence,
            role="object",
        )

    claim_type = refine_claim_type(
        extracted.claim_type.strip(),
        predicate,
        subj_type,
        obj_type,
    )

    claim_object = obj_ent.canonical_name if obj_ent else (target or context[:255])
    source_hash = compute_entity_source_hash(
        subj_ent.id,
        predicate,
        obj_ent.id if obj_ent else None,
        claim_type,
        polarity=extracted.polarity,
    )
    return ResolvedClaimFields(
        subject=subj_ent.canonical_name,
        predicate=predicate,
        claim_object=claim_object,
        claim_type=claim_type,
        subject_entity_id=subj_ent.id,
        object_entity_id=obj_ent.id if obj_ent else None,
        source_hash=source_hash,
        polarity=extracted.polarity,
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
    polarity: bool = True,
) -> ResolvedClaimFields:
    context = (claim_text or f"{subject} {predicate} {claim_object}").strip()
    ct_in = (claim_type or "relationship_state").strip()
    pred = predicate.strip()
    if pred.lower() in _CLAIM_TYPE_SLUGS:
        pred = infer_predicate_from_claim(ct_in, context)

    subj_type, _ = classify_entity_surface(
        subject.strip(), sentence=context, role="subject"
    )
    subj_ent = get_or_create_entity(
        db,
        story_id,
        subject.strip(),
        subj_type,
        sentence=context,
        role="subject",
    )

    obj_ent = None
    obj_type = None
    if claim_object.strip():
        obj_type, _ = classify_entity_surface(
            claim_object.strip(), sentence=context, role="object"
        )
        obj_ent = get_or_create_entity(
            db,
            story_id,
            claim_object.strip(),
            obj_type,
            sentence=context,
            role="object",
        )

    ct = refine_claim_type(ct_in, pred, subj_type, obj_type)

    source_hash = compute_entity_source_hash(
        subj_ent.id,
        pred,
        obj_ent.id if obj_ent else None,
        ct,
        polarity=polarity,
    )
    return ResolvedClaimFields(
        subject=subj_ent.canonical_name,
        predicate=pred,
        claim_object=obj_ent.canonical_name if obj_ent else claim_object.strip(),
        claim_type=ct,
        subject_entity_id=subj_ent.id,
        object_entity_id=obj_ent.id if obj_ent else None,
        source_hash=source_hash,
        polarity=polarity,
    )


def rehash_claim_row(claim: Claim) -> str:
    polarity = getattr(claim, "polarity", True)
    if claim.subject_entity_id:
        return compute_entity_source_hash(
            claim.subject_entity_id,
            claim.predicate,
            claim.object_entity_id,
            claim.claim_type or "",
            polarity=polarity,
        )
    return source_hash_for_claim_row(
        claim.subject,
        claim.predicate,
        claim.claim_object,
        claim.claim_type,
        polarity=polarity,
    )
