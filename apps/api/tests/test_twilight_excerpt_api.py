"""
Twilight excerpt — entity typing + relationship graph invariants (ChatGPT spec).

Uses POST /stories/{id}/scenes (not /chapters). Deterministic extraction: no OpenAI in tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.entity_classification import (
    classify_entity_surface,
    should_render_relationship_edge,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TWILIGHT_EXCERPT = FIXTURE_DIR / "twilight_excerpt.txt"
POV = "Bella"

NON_CHARACTER_SURFACES = [
    ("water", "concept"),
    ("sun", "concept"),
    ("the sun", "concept"),
    ("heat", "concept"),
    ("the heat", "concept"),
    ("rain", "concept"),
    ("truck", "object"),
    ("car", "object"),
    ("Chevy", "object"),
    ("airport", "object"),
    ("parka", "object"),
    ("cruiser", "object"),
]

CHARACTER_SURFACES = [
    "Bella",
    "Charlie",
    "Phil",
    "Billy Black",
    "Renée",
    "Renee",
]

PLACE_SURFACES = [
    "Phoenix",
    "Forks",
    "Seattle",
    "Port Angeles",
    "La Push",
    "California",
    "Olympic Peninsula",
    "Washington State",
    "United States of America",
]


def load_twilight_excerpt() -> str:
    path = TWILIGHT_EXCERPT
    if not path.is_file():
        path = FIXTURE_DIR / "twilight_chapter1_opening.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def twilight_text() -> str:
    return load_twilight_excerpt()


def _save_chapter(client, story_id: int, text: str) -> dict:
    r = client.post(
        f"/stories/{story_id}/scenes",
        json={
            "scene_number": 1,
            "text": text,
            "pov_character": POV,
            "claims": [],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def no_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    def _no_llm(*_a, **_k):
        return [], False, False, False, 0, False, 0

    from app.extraction import extract as extract_mod

    monkeypatch.setattr(extract_mod, "_llm_extract_chunk", _no_llm)


def test_twilight_surface_entity_classification(twilight_text: str):
    """Non-characters must not be typed as character (objects, places, concepts)."""
    for name, expected in NON_CHARACTER_SURFACES:
        etype, _ = classify_entity_surface(
            name,
            sentence=twilight_text[:500],
            role="object",
        )
        assert etype == expected, f"{name!r} expected {expected}, got {etype}"

    for name in CHARACTER_SURFACES:
        etype, _ = classify_entity_surface(name, role="subject")
        assert etype == "character", f"{name!r} should be character, got {etype}"

    for name in PLACE_SURFACES:
        etype, _ = classify_entity_surface(
            name,
            sentence=twilight_text[:500],
            role="object",
        )
        assert etype == "place", f"{name!r} should be place, got {etype}"


def test_should_render_relationship_edge_rule():
    assert should_render_relationship_edge(
        "relationship_state", "character", "character"
    )
    assert not should_render_relationship_edge(
        "relationship_state", "character", "concept"
    )
    assert not should_render_relationship_edge(
        "character_preference", "character", "place"
    )
    assert not should_render_relationship_edge(
        "relationship_state", "character", "place"
    )
    assert not should_render_relationship_edge(
        "relationship_state", "character", "object"
    )


def test_twilight_excerpt_entities_after_analyze(client, no_openai, twilight_text: str):
    r = client.post("/stories", json={"title": "Excerpt Test"})
    assert r.status_code == 200
    story_id = r.json()["id"]

    _save_chapter(client, story_id, twilight_text)

    entities = client.get(f"/stories/{story_id}/entities").json()
    by_name = {e["canonical_name"].lower(): e for e in entities}
    by_type = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], set()).add(e["canonical_name"].lower())

    characters = by_type.get("character", set())
    places = by_type.get("place", set())
    objects_concepts = (by_type.get("object", set()) | by_type.get("concept", set()))

    assert "bella" in characters

    assert "phoenix" in places or "phoenix" in {n for n in by_name if by_name[n]["entity_type"] == "place"}
    if "phoenix" in by_name:
        assert by_name["phoenix"]["entity_type"] == "place"

    for bad in (
        "water",
        "sun",
        "heat",
        "truck",
        "car",
        "airport",
        "her wide",
        "the vigorous",
    ):
        assert bad not in characters, f"{bad} must not be a character entity"

    for name, _ in NON_CHARACTER_SURFACES:
        key = name.lower()
        if key in by_name:
            assert by_name[key]["entity_type"] != "character"


def test_relationship_graph_only_character_to_character_edges(
    client, no_openai, twilight_text: str
):
    r = client.post("/stories", json={"title": "Excerpt Graph"})
    story_id = r.json()["id"]
    scene = _save_chapter(client, story_id, twilight_text)
    scene_id = scene["id"]

    detail = client.get(f"/stories/{story_id}/scenes/{scene_id}").json()
    for claim in detail["claims"]:
        client.patch(
            f"/stories/{story_id}/scenes/{scene_id}/claims/{claim['id']}",
            json={"status": "approved"},
        )

    graph = client.get(f"/stories/{story_id}/relationship-graph").json()
    node_by_id = {n["id"]: n for n in graph["nodes"]}

    for edge in graph["edges"]:
        assert edge["source"] in node_by_id
        assert edge["target"] in node_by_id
        source = node_by_id[edge["source"]]
        target = node_by_id[edge["target"]]
        assert source["type"] == "character"
        assert target["type"] == "character"

    forbidden = ("water", "sun", "phoenix", "forks", "truck", "car", "heat", "airport")
    for edge in graph["edges"]:
        src = node_by_id[edge["source"]]["label"].lower()
        tgt = node_by_id[edge["target"]]["label"].lower()
        pred = (edge.get("predicate") or "").lower()
        for token in forbidden:
            assert token not in src, f"forbidden {token!r} in source {src!r}"
            assert token not in tgt, f"forbidden {token!r} in target {tgt!r}"
            assert token not in pred
