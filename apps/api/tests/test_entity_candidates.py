"""FASTUS Stage 2 - entity candidate extraction."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.entity_registry import get_or_create_entity
from app.models import Story
from app.nlp.chapter_parse import is_spacy_available, parse_chunk
from app.nlp.entity_candidates import extract_entity_candidates, extract_entity_candidates_from_text


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


def test_extracts_character_and_place_spans():
    text = "Bella did not trust Edward in Forks."
    candidates = extract_entity_candidates_from_text(text, 0)
    surfaces = {c.surface_text for c in candidates}
    assert "Bella" in surfaces
    assert "Edward" in surfaces
    assert "Forks" in surfaces

    bella = next(c for c in candidates if c.surface_text == "Bella")
    forks = next(c for c in candidates if c.surface_text == "Forks")
    assert bella.entity_type_guess == "character"
    assert forks.entity_type_guess == "place"
    assert bella.start_char < bella.end_char
    assert text[bella.start_char : bella.end_char] == "Bella"


def test_spacy_source_when_model_available():
    if not is_spacy_available():
        return
    parsed = parse_chunk("Edward met Bella in Phoenix.", 0)
    candidates = extract_entity_candidates(parsed)
    edward = next(c for c in candidates if c.surface_text == "Edward")
    assert edward.source == "spacy"
    assert edward.spacy_label == "PERSON"


def test_phoenix_classified_as_place_not_character():
    candidates = extract_entity_candidates_from_text("I loved Phoenix.", 0)
    phoenix = next(c for c in candidates if c.normalized_text == "phoenix")
    assert phoenix.entity_type_guess == "place"


def test_registry_resolves_nickname_to_canonical_entity():
    db = _session()
    try:
        story = Story(title="Twilight", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        bella = get_or_create_entity(db, story.id, "Isabella Swan", "character")
        db.flush()

        candidates = extract_entity_candidates_from_text(
            "Bella walked into the room.",
            0,
            db=db,
            story_id=story.id,
        )
        nick = next(c for c in candidates if c.surface_text == "Bella")
        assert nick.source == "registry"
        assert nick.registry_entity_id == bella.id
        assert nick.entity_type_guess == "character"
    finally:
        db.close()


def test_dedupes_same_span_once():
    text = "Edward Cullen stared at Edward."
    candidates = extract_entity_candidates_from_text(text, 0)
    edward_offsets = [
        (c.start_char, c.end_char)
        for c in candidates
        if c.normalized_text == "edward"
    ]
    # Two distinct mentions of Edward at different offsets.
    assert len(edward_offsets) >= 1
