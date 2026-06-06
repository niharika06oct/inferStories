"""
Twilight Ch.1 opening — documents how structural + entity-aware extraction behaves today.

Without OPENAI_API_KEY the pipeline uses regex structural patterns + light heuristics (no LLM).
With a key, OpenAI may add richer character_state / timeline claims; those are not asserted here.

Expected *relationship map* edges: only approved character↔character relationship_state claims.
This passage is mostly interior monologue and preferences (loves Phoenix, loves the sun), so the
graph is often empty after classification — by design.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_entities import resolve_extracted
from app.database import Base
from app.entity_classification import classify_entity_surface
from app.extraction.extract import extract_claims_from_text
from app.extraction.persist import merge_extracted_claims_for_scene
from app.extraction.structural import detect_entities
from app.models import Claim, Entity, Scene, Story
from app.relationship_graph import build_relationship_graph

FIXTURE = Path(__file__).parent / "fixtures" / "twilight_chapter1_opening.txt"
POV = "Bella"


def _chapter_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


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


def _structural_only_extract(text: str):
    """Deterministic extraction: structural + empty LLM/heuristic chunk pass."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "")
    try:
        from app.extraction import extract as extract_mod

        def _no_llm(*_a, **_k):
            return [], False, False, False

        monkeypatch.setattr(extract_mod, "_llm_extract_chunk", _no_llm)
        return extract_claims_from_text(text, pov_character=POV)
    finally:
        monkeypatch.undo()


@pytest.fixture
def chapter_text() -> str:
    assert FIXTURE.is_file(), f"Missing fixture: {FIXTURE}"
    return _chapter_text()


def test_twilight_fixture_is_single_chunk(chapter_text: str):
  wc = len(chapter_text.split())
  assert wc < 3000, "Fixture should stay one chunk for predictable structural counts"


def test_twilight_detects_core_proper_names(chapter_text: str):
    names = {n.lower() for n in detect_entities(chapter_text)}
    # Regex NER is noisy (also picks You, Tell Charlie, etc.) but hits protagonists.
    assert {"bella", "charlie", "phoenix", "forks"}.issubset(names)


def test_twilight_structural_love_preferences_with_pov(chapter_text: str):
    result = _structural_only_extract(chapter_text)
    assert result.structural_entity_count >= 10

    by_evidence = {(c.evidence or "").strip().lower(): c for c in result.claims}
    assert "i loved phoenix" in by_evidence
    assert any("loved the sun" in k for k in by_evidence)

    phoenix = by_evidence["i loved phoenix"]
    sun_key = next(k for k in by_evidence if "loved the sun" in k)
    sun = by_evidence[sun_key]
    assert phoenix.subject == POV
    assert sun.subject == POV
    assert phoenix.predicate == "loves"
    assert phoenix.target == "Phoenix"
    assert sun.target == "the sun"


def test_twilight_detested_forks_extracted(chapter_text: str):
    result = _structural_only_extract(chapter_text)
    assert any(
        "detest" in (c.evidence or "").lower() or "distaste" in (c.evidence or "").lower()
        for c in result.claims
    )


def test_twilight_resolved_preferences_are_not_graph_relationships(chapter_text: str):
    db = _session()
    try:
        story = Story(title="Twilight", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(
            story_id=story.id,
            scene_number=1,
            text=chapter_text,
            pov_character=POV,
        )
        db.add(scene)
        db.flush()

        result = _structural_only_extract(chapter_text)
        merge_extracted_claims_for_scene(db, scene, result.claims)
        db.flush()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(rows) >= 2

        phoenix_row = next(
            r for r in rows if "phoenix" in (r.evidence_text or "").lower()
        )
        assert phoenix_row.claim_type in ("character_preference", "place_preference")
        obj_ent = db.get(Entity, phoenix_row.object_entity_id)
        assert obj_ent is not None
        assert obj_ent.entity_type == "place"

        for row in rows:
            if row.claim_type == "character_preference":
                row.status = "approved"
        db.commit()

        graph = build_relationship_graph(db, story.id)
        # Preferences must not create character↔character edges on the map.
        assert not any(e.get("predicate") == "loves" for e in graph["edges"])
        labels = {n["label"].lower() for n in graph["nodes"]}
        assert "phoenix" not in labels
        assert "the sun" not in labels
        assert "water" not in labels
    finally:
        db.close()


def test_twilight_entity_types_for_preferences():
    phoenix_type, _ = classify_entity_surface(
        "Phoenix",
        sentence="I loved Phoenix.",
        evidence="I loved Phoenix",
        role="object",
    )
    sun_type, _ = classify_entity_surface(
        "the sun",
        sentence="I loved the sun and the blistering heat.",
        evidence="I loved the sun",
        role="object",
    )
    bella_type, _ = classify_entity_surface("Bella", role="subject")
    assert bella_type == "character"
    assert phoenix_type == "place"
    assert sun_type == "concept"


def test_twilight_resolved_claim_fields(chapter_text: str):
    db = _session()
    try:
        story = Story(title="Twilight resolve", description=None, owner_user_id="u")
        db.add(story)
        db.flush()

        result = _structural_only_extract(chapter_text)
        phoenix_claim = next(
            c for c in result.claims if (c.evidence or "").strip() == "I loved Phoenix"
        )
        resolved = resolve_extracted(db, story.id, phoenix_claim)
        assert resolved.subject == POV
        assert resolved.claim_type in ("character_preference", "place_preference")
        assert resolved.predicate == "loves"
        assert "phoenix" in resolved.claim_object.lower()
    finally:
        db.close()


def test_twilight_junk_claims_filtered(chapter_text: str):
    result = _structural_only_extract(chapter_text)
    evidences = {(c.evidence or "").lower() for c in result.claims}
    assert "as i stared at her wide" not in evidences
    assert not any("my mom said to me" in e for e in evidences)
