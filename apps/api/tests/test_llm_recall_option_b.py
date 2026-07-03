"""Option B: LLM recall first + FASTUS grounding + deterministic safety."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.extraction.claim_filter import filter_extracted_claims, should_reject_extracted_claim
from app.extraction.evidence_anchor import (
    apply_evidence_anchoring,
    evidence_anchored_in_text,
    strict_anchoring_enabled,
)
from app.extraction.extract import extract_claims_from_text, resolve_extracted_status
from app.extraction.llm_recall import RecallResult, clear_recall_cache
from app.extraction.schema import ExtractedClaim
from app.extraction.source_dedupe import claim_identity_key, merge_source_claims
from app.models import Claim, Scene, Story
from app.validation import validate_scene_claims

FIXTURE = Path(__file__).parent / "fixtures" / "twilight_chapter13_excerpt.txt"
POV = "Isabella Swan"


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


def _chapter_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _mock_recall_claims() -> list[dict]:
    """Simulated Stage 6a output for the Chapter 13 excerpt."""
    return [
        {
            "subject": "Charlie",
            "predicate": "father_of",
            "object": "Isabella Swan",
            "claim_type": "relationship_state",
            "claim": "Charlie is not the father of Isabella Swan.",
            "polarity": False,
            "evidence": "Charlie was not my father.",
            "confidence": 0.92,
            "importance": "high",
        },
        {
            "subject": "Isabella Swan",
            "predicate": "trusts",
            "object": "Charlie",
            "claim_type": "relationship_state",
            "claim": "Isabella Swan does not trust Charlie.",
            "polarity": False,
            "evidence": "I did not trust him at all.",
            "confidence": 0.88,
            "importance": "high",
        },
        {
            "subject": "Renée",
            "predicate": "mother_of",
            "object": "Isabella Swan",
            "claim_type": "relationship_state",
            "claim": "Renée is not the mother of Isabella Swan.",
            "polarity": False,
            "evidence": "My mother was not Renée",
            "confidence": 0.9,
            "importance": "high",
        },
        {
            "subject": "Edward",
            "predicate": "hostile_toward",
            "object": "Isabella Swan",
            "claim_type": "relationship_state",
            "claim": "Edward is hostile toward Isabella Swan.",
            "polarity": True,
            "evidence": "He was hostile toward me whenever I was near.",
            "confidence": 0.85,
            "importance": "medium",
        },
        {
            "subject": "Edward",
            "predicate": "loves",
            "object": "Isabella Swan",
            "claim_type": "relationship_state",
            "claim": "Edward does not love Isabella Swan.",
            "polarity": False,
            "evidence": "Edward did not love me.",
            "confidence": 0.87,
            "importance": "high",
        },
        {
            "subject": "Cullens",
            "predicate": "lived_in",
            "object": "Phoenix",
            "claim_type": "timeline_fact",
            "claim": "The Cullens lived in Phoenix.",
            "polarity": True,
            "evidence": "The Cullens had lived in Phoenix before",
            "confidence": 0.8,
            "importance": "medium",
        },
        {
            "subject": "did",
            "predicate": "trusts",
            "object": "him at all",
            "claim_type": "relationship_state",
            "claim": "did not trust him at all.",
            "polarity": False,
            "evidence": "did not trust him at all",
            "confidence": 0.5,
            "importance": "low",
        },
    ]


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_recall_cache()
    yield
    clear_recall_cache()


def test_evidence_anchoring_detects_quotes():
    text = _chapter_text()
    assert evidence_anchored_in_text(text, evidence="Charlie was not my father.")
    assert not evidence_anchored_in_text(text, evidence="completely invented quote")


def test_unanchored_llm_claim_gets_needs_review(monkeypatch):
    monkeypatch.delenv("FASTUS_STRICT_ANCHORING", raising=False)
    claim = ExtractedClaim(
        subject="Charlie",
        claim_type="relationship_state",
        predicate="father_of",
        target="Isabella Swan",
        claim="The volcano erupted without warning.",
        polarity=False,
        confidence=0.9,
        evidence="invented subtext not in passage",
        generation_origin="llm_recall",
        importance="high",
    )
    anchored = apply_evidence_anchoring(claim, _chapter_text())
    assert anchored.anchored is False
    assert resolve_extracted_status(anchored) == "needs_review"
    assert anchored.confidence < 0.9


def test_anchored_high_confidence_stays_suggested_not_auto_approved():
    claim = ExtractedClaim(
        subject="Charlie",
        claim_type="relationship_state",
        predicate="father_of",
        target="Isabella Swan",
        claim="Charlie is not the father of Isabella Swan.",
        polarity=False,
        confidence=0.92,
        evidence="Charlie was not my father.",
        generation_origin="llm_recall",
    )
    anchored = apply_evidence_anchoring(claim, _chapter_text())
    assert anchored.anchored is True
    assert resolve_extracted_status(anchored) == "suggested"


def test_source_dedupe_merges_fastus_and_recall():
    recall = ExtractedClaim(
        subject="Charlie",
        claim_type="relationship_state",
        predicate="father_of",
        target="Isabella Swan",
        claim="Charlie is not the father of Isabella Swan.",
        polarity=False,
        confidence=0.85,
        evidence="Charlie was not my father.",
        generation_origin="llm_recall",
        anchored=True,
    )
    fastus = ExtractedClaim(
        subject="Charlie",
        claim_type="relationship_state",
        predicate="father_of",
        target="Isabella Swan",
        claim="Charlie is not the father of Isabella Swan.",
        polarity=False,
        confidence=0.78,
        evidence="Charlie was not my father. He was a stranger.",
        generation_origin="fastus",
        anchored=True,
    )
    merged = merge_source_claims([recall, fastus])
    assert len(merged) == 1
    assert "fastus" in merged[0].generation_origin
    assert merged[0].confidence >= 0.85


def test_fragment_claim_rejected_by_stage0():
    fragment = ExtractedClaim(
        subject="did",
        claim_type="relationship_state",
        predicate="trusts",
        target="him at all",
        claim="did not trust him at all.",
        polarity=False,
        confidence=0.5,
        evidence="did not trust him at all",
        generation_origin="llm_recall",
    )
    assert should_reject_extracted_claim(fragment)


def test_llm_first_pipeline_with_mocked_recall(monkeypatch):
    monkeypatch.setenv("FASTUS_LLM_FIRST", "1")
    monkeypatch.setenv("FASTUS_LLM_REFINE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("FASTUS_STRICT_ANCHORING", raising=False)

    text = _chapter_text()

    def _fake_recall(*_a, **_k):
        claims = [
            ExtractedClaim(
                subject=item["subject"],
                claim_type=item["claim_type"],
                predicate=item["predicate"],
                target=item["object"],
                claim=item["claim"],
                polarity=item["polarity"],
                confidence=item["confidence"],
                evidence=item["evidence"],
                chunk_index=0,
                generation_origin="llm_recall",
                importance=item.get("importance", "medium"),
            )
            for item in _mock_recall_claims()
        ]
        return RecallResult(claims=claims, attempted=True, ok=True, raw_count=len(claims))

    monkeypatch.setattr(
        "app.extraction.extract.recall_claims_from_chunk",
        _fake_recall,
    )

    result = extract_claims_from_text(text, pov_character=POV)
    assert result.llm_recall_total >= 5
    assert result.after_dedupe_total > 0
    assert result.anchored_total > 0

    filtered = filter_extracted_claims(result.claims, pov_character=POV)
    assert not any(c.subject.lower() == "did" for c in filtered)

    by_key = {
        (
            c.subject.lower(),
            c.predicate,
            c.target.lower(),
            c.polarity,
        ): c
        for c in filtered
    }
    father = next(
        (c for c in filtered if c.predicate == "father_of" and "charlie" in c.subject.lower()),
        None,
    )
    assert father is not None
    assert father.polarity is False

    trust = next(
        (c for c in filtered if c.predicate == "trusts" and c.polarity is False),
        None,
    )
    if trust:
        assert "him at all" not in (trust.target or "").lower()


def test_polarity_flip_hard_contradiction_with_recall_claims():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Charlie is my father.")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Charlie",
                predicate="father_of",
                claim_object="Isabella Swan",
                polarity=True,
                claim_type="relationship_state",
                status="approved",
                is_major_plotline=True,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=13, text=_chapter_text())
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Charlie",
            predicate="father_of",
            claim_object="Isabella Swan",
            polarity=False,
            claim_type="relationship_state",
            status="needs_review",
            evidence_text="Charlie was not my father.",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].judge_classification == "hard_contradiction"
    finally:
        db.close()


def test_strict_anchoring_drops_unanchored_recall(monkeypatch):
    monkeypatch.setenv("FASTUS_STRICT_ANCHORING", "1")
    assert strict_anchoring_enabled()
    from app.extraction.evidence_anchor import filter_unanchored_if_strict

    claims = [
        ExtractedClaim(
            subject="X",
            claim_type="character_state",
            predicate="knows",
            target="Y",
            claim="X knows Y.",
            confidence=0.8,
            evidence="not in text",
            generation_origin="llm_recall",
            anchored=False,
        )
    ]
    kept, dropped = filter_unanchored_if_strict(claims)
    assert dropped == 1
    assert kept == []
