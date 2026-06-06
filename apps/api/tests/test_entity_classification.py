"""Entity type classification and claim-type refinement."""

from app.claim_entities import resolve_extracted
from app.entity_classification import (
    classify_entity_surface,
    is_character_to_character_relationship,
    refine_claim_type,
)
from app.extraction.schema import ExtractedClaim


def test_water_is_not_character():
    etype, conf = classify_entity_surface(
        "water",
        sentence="She still loves the water.",
        role="object",
    )
    assert etype == "concept"
    assert conf >= 0.7


def test_proper_names_are_characters():
    etype, _ = classify_entity_surface("Niharika", role="subject")
    assert etype == "character"
    etype2, _ = classify_entity_surface("Abhilash", role="object")
    assert etype2 == "character"


def test_human_role_phrase_is_character():
    etype, _ = classify_entity_surface(
        "the man on the shack",
        sentence="The man on the shack loves Niharika.",
        role="subject",
    )
    assert etype == "character"


def test_refine_loves_water_to_preference():
    ct = refine_claim_type(
        "relationship_state",
        "loves",
        "character",
        "concept",
    )
    assert ct == "character_preference"


def test_refine_loves_place_to_place_preference():
    ct = refine_claim_type(
        "relationship_state",
        "loves",
        "character",
        "place",
    )
    assert ct == "place_preference"


def test_refine_detest_place_to_place_preference():
    ct = refine_claim_type(
        "relationship_state",
        "detests",
        "character",
        "place",
    )
    assert ct == "place_preference"


def test_refine_loves_person_to_relationship():
    ct = refine_claim_type(
        "relationship_state",
        "loves",
        "character",
        "character",
    )
    assert ct == "relationship_state"


def test_graph_edge_gate():
    assert is_character_to_character_relationship(
        "relationship_state", "character", "character"
    )
    assert not is_character_to_character_relationship(
        "relationship_state", "character", "concept"
    )
    assert not is_character_to_character_relationship(
        "character_preference", "character", "concept"
    )


def test_resolve_extracted_water_preference():
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.models import Entity, Scene, Story

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
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        story = Story(title="t", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        db.add(Scene(story_id=story.id, scene_number=1, text="x"))
        db.flush()

        resolved = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Niharika",
                target="water",
                claim="Niharika loves the water.",
                claim_type="relationship_state",
                predicate="loves",
                evidence="She still loves the water.",
                confidence=0.8,
            ),
        )
        db.commit()

        water = (
            db.query(Entity)
            .filter(Entity.story_id == story.id, Entity.canonical_name.ilike("%water%"))
            .one()
        )
        assert water.entity_type == "concept"
        assert resolved.claim_type == "character_preference"
        assert resolved.object_entity_id == water.id
    finally:
        db.close()
