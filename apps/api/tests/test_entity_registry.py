"""Entity registry: alias resolution and entity-aware claim hashing."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_entities import resolve_extracted
from app.claim_identity import compute_entity_source_hash
from app.database import Base
from app.entity_registry import find_entity_by_name, get_or_create_entity
from app.extraction.persist import merge_extracted_claims_for_scene
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Entity, Scene, Story


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


def test_jon_resolves_to_jon_snow():
    db = _session()
    try:
        story = Story(title="W", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        snow = get_or_create_entity(db, story.id, "Jon Snow", "character")
        db.flush()
        jon = get_or_create_entity(db, story.id, "Jon", "character")
        assert jon.id == snow.id
        assert find_entity_by_name(db, story.id, "Jon Snow") is not None
        assert find_entity_by_name(db, story.id, "Jon").id == snow.id
    finally:
        db.close()


def test_entity_source_hash_uses_ids():
    h1 = compute_entity_source_hash(1, "distrusts", 2, "relationship_state")
    h2 = compute_entity_source_hash(1, "distrusts", 2, "relationship_state")
    h3 = compute_entity_source_hash(1, "trusts", 2, "relationship_state")
    assert h1 == h2
    assert h1 != h3


def test_extracted_claim_predicate_not_claim_type():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        resolved = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Nahira",
                claim_type="relationship_state",
                predicate="distrusts",
                target="Stefan",
                claim="Nahira distrusts Stefan.",
                confidence=0.9,
                canon_level="active",
                evidence="Nahira distrusts Stefan.",
                chunk_index=0,
            ),
        )
        assert resolved.predicate == "distrusts"
        assert resolved.claim_type == "relationship_state"

        merge_extracted_claims_for_scene(
            db,
            scene,
            [
                ExtractedClaim(
                    subject="Nahira",
                    claim_type="relationship_state",
                    predicate="distrusts",
                    target="Stefan",
                    claim="Nahira distrusts Stefan.",
                    confidence=0.9,
                    canon_level="active",
                    evidence="Nahira distrusts Stefan.",
                    chunk_index=0,
                )
            ],
        )
        row = db.query(Claim).filter(Claim.scene_id == scene.id).one()
        assert row.predicate == "distrusts"
        assert row.claim_type == "relationship_state"
        assert row.subject_entity_id is not None
        assert row.object_entity_id is not None
        assert db.query(Entity).filter(Entity.story_id == story.id).count() == 2
    finally:
        db.close()
