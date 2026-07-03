"""Location hierarchy: residence inside city is compatible; two cities are not."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.location_compatibility import (
    classify_place_granularity,
    is_location_predicate,
    location_facts_compatible,
    locations_are_compatible,
    refine_location_predicate,
)
from app.models import Claim, Scene, Story
from app.validation import validate_scene_claims


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


def test_classify_residence_vs_city():
    assert classify_place_granularity("Charlie's house") == "residence"
    assert classify_place_granularity("Forks High School") == "institution"
    assert classify_place_granularity("Forks") == "city"
    assert classify_place_granularity("Phoenix") == "city"


def test_school_and_house_are_compatible():
    assert locations_are_compatible("Forks High School", "Charlie's house")
    assert locations_are_compatible("Charlie's house", "Forks High School")


def test_refine_does_not_map_school_to_lives_at():
    from app.location_compatibility import refine_location_predicate

    assert refine_location_predicate("lives_in", "Forks High School") == "lives_in"
    assert refine_location_predicate("in", "Forks High School") == "in"


def test_locations_are_compatible_house_in_city():
    assert locations_are_compatible("Charlie's house", "Forks")
    assert locations_are_compatible("Forks", "Charlie's house")


def test_locations_are_incompatible_two_cities():
    assert not locations_are_compatible("Phoenix", "Forks")
    assert not locations_are_compatible("Forks", "Phoenix")


def test_refine_location_predicate_splits_in_at():
    assert refine_location_predicate("in", "Forks", evidence="moved to Forks") == "lives_in"
    assert (
        refine_location_predicate("in", "Charlie's house", evidence="at Charlie's house")
        == "lives_at"
    )
    assert refine_location_predicate("lives_in", "Charlie's house") == "lives_at"


def test_is_location_predicate_covers_lives_at():
    assert is_location_predicate("lives_at")
    assert is_location_predicate("lives in")


def test_validation_skips_exclusive_object_for_school_and_house():
    db = _session()
    try:
        story = Story(title="school-house", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=3, text="School day.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Isabella Swan",
                predicate="lives_at",
                claim_object="Forks High School",
                status="approved",
                evidence_text="I was expected, a topic of gossip no doubt.",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=6, text="Heading home.")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Isabella Swan",
            predicate="lives_at",
            claim_object="Charlie's house",
            status="suggested",
            evidence_text="I headed back to Charlie's house, fighting tears the whole way there.",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_validation_skips_exclusive_object_for_house_and_city():
    db = _session()
    try:
        story = Story(title="location-hierarchy", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Charlie's house in Forks.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Bella",
                predicate="lives_at",
                claim_object="Charlie's house",
                status="approved",
                evidence_text="I was staying at Charlie's house.",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="Forks arrival.")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="lives in",
            claim_object="Forks",
            status="suggested",
            evidence_text="It was to Forks that I now exiled myself.",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_validation_still_conflicts_phoenix_vs_forks():
    db = _session()
    try:
        story = Story(title="two-cities", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Bella",
                predicate="lives in",
                claim_object="Phoenix",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="lives in",
            claim_object="Forks",
            status="suggested",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert len(issues) == 1
        assert issues[0].conflict_kind == "exclusive_object"
    finally:
        db.close()


def test_location_facts_compatible_uses_entity_granularity():
    db = _session()
    try:
        story = Story(title="entity-gran", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        from app.entity_registry import get_or_create_entity

        forks = get_or_create_entity(db, story.id, "Forks", "place")
        house = get_or_create_entity(
            db,
            story.id,
            "Charlie's house",
            "place",
            evidence="Charlie's house in Forks",
        )
        db.flush()

        assert forks.place_granularity == "city"
        assert house.place_granularity == "residence"

        assert location_facts_compatible(
            db,
            old_object="Charlie's house",
            new_object="Forks",
            old_object_entity_id=house.id,
            new_object_entity_id=forks.id,
        )
    finally:
        db.close()
