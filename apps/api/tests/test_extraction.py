"""Automatic claim extraction on chapter save."""

import pytest

from app.extraction.chunking import chunk_chapter_text
from app.extraction.extract import extract_claims_from_text, status_for_confidence


def test_chunk_short_chapter():
    text = "word " * 500
    chunks, warn = chunk_chapter_text(text)
    assert len(chunks) == 1
    assert warn is None


def test_chunk_long_chapter():
    text = "word " * 5000
    chunks, _warn = chunk_chapter_text(text)
    assert len(chunks) >= 2


def test_status_for_confidence():
    assert status_for_confidence(0.95) == "approved"
    assert status_for_confidence(0.75) == "needs_review"
    assert status_for_confidence(0.5) == "suggested"


def test_heuristic_extract_trust(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = "Asha trusts Rohan in the moonlit hall."
    result = extract_claims_from_text(text)
    assert result.source in ("heuristic", "hybrid")
    assert any("trust" in c.claim.lower() for c in result.claims)
    assert result.duration_ms >= 0
    assert len(result.chunks) >= 1


def test_structural_entities_and_interaction():
    text = "Nahira looked at Ashan on the beach in Goa."
    result = extract_claims_from_text(text)
    assert result.structural_entity_count >= 2
    assert any("Nahira" in e or "Ashan" in e for c in result.chunks for e in c.entities)


def test_fastus_debug_instrumentation_on_extract(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = "Charlie was not my father. Bella did not trust Edward in Forks."
    result = extract_claims_from_text(text, pov_character="Isabella Swan")
    assert result.fastus_events
    assert result.chunks[0].fastus_token_count > 0
    assert result.chunks[0].fastus_entity_candidate_count >= 1
    stages = {e.stage for e in result.fastus_events}
    assert "0" in stages or "1" in stages
    assert "1" in stages
    assert "2" in stages
    assert "3" in stages
    assert "6" in stages
    assert any(e.event == "parse" for e in result.fastus_events)
    assert any(e.event == "llm_refine" for e in result.fastus_events)
    assert any(e.event == "entity_candidates" for e in result.fastus_events)


def test_auto_extract_on_scene_save(client):
    r = client.post("/stories", json={"title": "Auto memory"})
    sid = r.json()["id"]
    r = client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Nahira still did not fully trust Stefan after the reveal.",
            "claims": [],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("extraction") is not None
    assert body["extraction"]["claim_count"] >= 1

    scene_id = body["id"]
    full = client.get(f"/stories/{sid}/scenes/{scene_id}")
    claims = full.json()["claims"]
    assert len(claims) >= 1
    assert claims[0]["source"] == "extracted"
    assert claims[0]["evidence_text"]


def test_claim_approve_endpoint(client):
    r = client.post("/stories", json={"title": "Review"})
    sid = r.json()["id"]
    r = client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan.",
            "claims": [],
        },
    )
    scene_id = r.json()["id"]
    full = client.get(f"/stories/{sid}/scenes/{scene_id}")
    claim_id = full.json()["claims"][0]["id"]
    r = client.patch(
        f"/stories/{sid}/scenes/{scene_id}/claims/{claim_id}",
        json={"status": "approved"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
