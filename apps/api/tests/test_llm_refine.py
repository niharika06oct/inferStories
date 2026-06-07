"""FASTUS Stage 6 — LLM candidate refinement."""

import json

import pytest

from app.extraction.llm_refine import (
    apply_refinements,
    build_candidate_payloads,
    clear_refine_cache,
    drafts_to_extracted_passthrough,
    refine_cache_key,
    refine_claim_drafts,
)
from app.extraction.semantic_patterns import relations_to_claim_drafts
from app.nlp.entity_candidates import extract_entity_candidates_from_text
from app.nlp.relation_candidates import extract_relation_candidates_from_text


def _drafts_for(text: str, *, pov: str = "Isabella Swan"):
    entities = extract_entity_candidates_from_text(text, pov_character=pov)
    relations = extract_relation_candidates_from_text(text, pov_character=pov)
    return relations_to_claim_drafts(relations, entities)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_refine_cache()
    yield
    clear_refine_cache()


def test_build_candidate_payloads_ids_and_fields():
    drafts = _drafts_for("Charlie was not my father.")
    payloads = build_candidate_payloads(drafts)
    assert payloads
    assert payloads[0]["candidate_id"] == "c0"
    assert payloads[0]["predicate"] == "father_of"
    assert payloads[0]["polarity"] is False
    assert "question" in payloads[0]


def test_apply_refinements_accepts_and_rejects():
    drafts = _drafts_for("Charlie was not my father.")
    refinements = [
        {
            "candidate_id": "c0",
            "valid": True,
            "claim_type": "relationship_state",
            "predicate": "father_of",
            "polarity": False,
            "confidence": 0.96,
            "explanation": "Explicit denial.",
        },
        {
            "candidate_id": "c99",
            "valid": False,
            "explanation": "unknown id",
        },
    ]
    claims, rejected = apply_refinements(drafts, refinements)
    assert len(claims) == 1
    assert claims[0].predicate == "father_of"
    assert claims[0].polarity is False
    assert claims[0].confidence == 0.96
    assert claims[0].generation_origin == "llm"
    assert rejected == 0


def test_apply_refinements_rejects_invalid_candidate():
    drafts = _drafts_for("Charlie was not my father.")
    refinements = [{"candidate_id": "c0", "valid": False, "explanation": "bad"}]
    claims, rejected = apply_refinements(drafts, refinements)
    assert claims == []
    assert rejected == 1


def test_passthrough_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    drafts = _drafts_for("Charlie was my father.")
    result = refine_claim_drafts(
        drafts,
        "Charlie was my father.",
        0,
        1,
        pov_character="Isabella Swan",
    )
    assert result.ok is True
    assert result.attempted is False
    assert len(result.claims) == len(drafts)
    assert all(c.generation_origin == "llm" for c in result.claims)


def test_cache_hit_avoids_second_api_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    drafts = _drafts_for("Edward did not trust Bella.")
    calls: list[str] = []

    def _fake_call(**_kwargs):
        calls.append("api")
        return [
            {
                "candidate_id": "c0",
                "valid": True,
                "claim_type": "relationship_state",
                "predicate": "trusts",
                "polarity": False,
                "confidence": 0.93,
            }
        ]

    monkeypatch.setattr(
        "app.extraction.llm_refine._call_openai_refine",
        lambda **_kw: _fake_call(),
    )

    text = "Edward did not trust Bella."
    r1 = refine_claim_drafts(drafts, text, 0, 1, pov_character="Isabella Swan")
    r2 = refine_claim_drafts(drafts, text, 0, 1, pov_character="Isabella Swan")

    assert len(calls) == 1
    assert r1.cache_hit is False
    assert r2.cache_hit is True
    assert r1.claims[0].predicate == "trusts"
    assert r2.claims[0].predicate == "trusts"


def test_refine_cache_key_stable():
    candidates = [{"candidate_id": "c0", "predicate": "trusts"}]
    k1 = refine_cache_key(model="gpt-4o-mini", pov_character="Bella", text="hi", candidates=candidates)
    k2 = refine_cache_key(model="gpt-4o-mini", pov_character="Bella", text="hi", candidates=candidates)
    assert k1 == k2
    k3 = refine_cache_key(model="gpt-4o-mini", pov_character="Bella", text="bye", candidates=candidates)
    assert k1 != k3


def test_drafts_to_extracted_passthrough_origin():
    drafts = _drafts_for("Charlie was my father.")
    claims = drafts_to_extracted_passthrough(drafts)
    assert claims
    assert claims[0].generation_origin == "llm"


def test_fastus_debug_includes_stage6_on_extract(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.extraction.extract import extract_claims_from_text

    result = extract_claims_from_text(
        "Charlie was not my father. Edward did not trust Bella.",
        pov_character="Isabella Swan",
    )
    stages = {e.stage for e in result.fastus_events}
    assert "6" in stages
    assert any(e.event == "llm_refine" for e in result.fastus_events)
    # No API key: FASTUS drafts passthrough as LLM-layer claims (deduped vs structural).
    assert result.chunks[0].fastus_llm_refined_count >= 1
