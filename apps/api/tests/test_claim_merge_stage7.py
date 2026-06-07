"""FASTUS Stage 7 — polarity-aware merge and temporal transitions."""

import json

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_entities import resolve_extracted
from app.claim_identity import compute_entity_source_hash
from app.database import Base
from app.extraction.merge import entity_pair_merge_key
from app.extraction.persist import (
    delete_replaceable_scene_claims,
    merge_extracted_claims_for_scene,
)
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene, Story


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _trust_claim(*, polarity: bool = True, target: str = "Rohan") -> ExtractedClaim:
    return ExtractedClaim(
        subject="Asha",
        claim_type="relationship_state",
        predicate="trusts",
        target=target,
        claim=f"Asha {'does not ' if not polarity else ''}trusts {target}.",
        polarity=polarity,
        confidence=0.9,
        canon_level="active",
        evidence=f"Asha trusts {target}.",
        chunk_index=0,
        generation_origin="llm",
    )


def test_entity_pair_key_includes_polarity():
    pos = entity_pair_merge_key(1, 2, "father_of", polarity=True)
    neg = entity_pair_merge_key(1, 2, "father_of", polarity=False)
    assert pos != neg


def test_opposite_polarity_inserts_separate_rows():
    db = _session()
    try:
        story = Story(title="pol", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        pos = resolve_extracted(db, story.id, _trust_claim(polarity=True))
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=pos.subject,
            predicate=pos.predicate,
            claim_object=pos.claim_object,
            polarity=True,
            subject_entity_id=pos.subject_entity_id,
            object_entity_id=pos.object_entity_id,
            claim_type=pos.claim_type,
            claim_text="Asha trusts Rohan.",
            status="approved",
            source="extracted",
            source_hash=pos.source_hash,
            claim_version=1,
            confidence=0.9,
        )
        db.add(approved)
        db.flush()

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [_trust_claim(polarity=False, target="Rohan")],
        )
        db.commit()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(rows) == 2
        polarities = {r.polarity for r in rows}
        assert polarities == {True, False}
    finally:
        db.close()


def test_same_polarity_reinforcement_bumps_version_and_history():
    db = _session()
    try:
        story = Story(title="reinf", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        resolved = resolve_extracted(db, story.id, _trust_claim())
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=resolved.subject,
            predicate=resolved.predicate,
            claim_object=resolved.claim_object,
            polarity=True,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            claim_type=resolved.claim_type,
            claim_text="Asha trusts Rohan.",
            status="approved",
            source="extracted",
            source_hash=resolved.source_hash,
            claim_version=2,
            confidence=0.88,
            confidence_history=json.dumps(
                [{"version": 2, "confidence": 0.88, "scene_id": scene.id}]
            ),
        )
        db.add(approved)
        db.flush()

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [
                ExtractedClaim(
                    subject="Asha",
                    claim_type="relationship_state",
                    predicate="trusts",
                    target="Rohan",
                    claim="Asha trusts Rohan deeply.",
                    polarity=True,
                    confidence=0.93,
                    canon_level="active",
                    evidence="Asha trusts Rohan deeply.",
                    chunk_index=0,
                )
            ],
        )
        db.refresh(approved)

        assert approved.claim_version == 3
        history = json.loads(approved.confidence_history or "[]")
        assert len(history) == 2
        assert history[-1]["confidence"] == 0.93
    finally:
        db.close()


def test_object_transition_closes_prior_and_opens_new():
    db = _session()
    try:
        story = Story(title="trans", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        rohan = resolve_extracted(db, story.id, _trust_claim(target="Rohan"))
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=rohan.subject,
            predicate=rohan.predicate,
            claim_object=rohan.claim_object,
            polarity=True,
            subject_entity_id=rohan.subject_entity_id,
            object_entity_id=rohan.object_entity_id,
            claim_type=rohan.claim_type,
            claim_text="Asha trusts Rohan.",
            status="approved",
            source="extracted",
            source_hash=rohan.source_hash,
            claim_version=1,
            valid_from_scene=scene.id,
            confidence=0.9,
        )
        db.add(approved)
        db.flush()

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [_trust_claim(target="Stefan")],
        )
        db.commit()

        rows = (
            db.query(Claim)
            .filter(Claim.scene_id == scene.id)
            .order_by(Claim.id)
            .all()
        )
        assert len(rows) == 2
        closed = next(r for r in rows if r.claim_object == "Rohan")
        opened = next(r for r in rows if r.claim_object == "Stefan")
        assert closed.valid_until_scene == scene.id
        assert opened.valid_from_scene == scene.id
        assert opened.valid_until_scene is None
    finally:
        db.close()


def test_polarity_flip_does_not_match_entity_pair_merge():
    """Negated father_of must not merge into positive row via entity-pair fallback."""
    pos_hash = compute_entity_source_hash(
        10, "father_of", 20, "relationship_state", polarity=True
    )
    neg_hash = compute_entity_source_hash(
        10, "father_of", 20, "relationship_state", polarity=False
    )
    assert pos_hash != neg_hash
    pos_pair = entity_pair_merge_key(10, 20, "father_of", polarity=True)
    neg_pair = entity_pair_merge_key(10, 20, "father_of", polarity=False)
    assert pos_pair != neg_pair
