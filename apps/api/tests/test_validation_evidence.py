from app.models import Claim
from app.validation_evidence import (
    claim_anchored_in_scene,
    continuity_anchor_in_scene,
    evidence_offset_in_scene,
    locate_claim_evidence_span,
)


def test_continuity_anchor_finds_evidence_quote():
    text = "She loved Phoenix. I detested Forks."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Bella",
        predicate="detests",
        claim_object="Forks",
        evidence_text="I detested Forks",
    )
    offset, anchor, length = continuity_anchor_in_scene(text, claim)
    assert offset == text.lower().index("i detested")
    assert "detested" in anchor.lower()
    assert length > 0


def test_continuity_anchor_does_not_use_subject_at_chapter_start():
    text = "Bella arrived. Later Charlie waved from the porch."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Charlie",
        predicate="waves",
        claim_object="",
        evidence_text="",
        claim_text="Charlie waved from the porch.",
    )
    offset, anchor, _ = continuity_anchor_in_scene(text, claim)
    assert offset == text.index("Charlie waved")
    assert anchor.lower().startswith("charlie waved")


def test_continuity_anchor_not_found_does_not_fake_offset():
    text = "Completely different prose."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Bella",
        predicate="detests",
        claim_object="Forks",
        evidence_text="I detested Forks",
    )
    offset, anchor, length = continuity_anchor_in_scene(text, claim)
    assert offset == 0
    assert length == 0
    assert "detested" in anchor.lower()


def test_evidence_offset_finds_quote():
    text = "She loved Phoenix. I detested Forks."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Bella",
        predicate="detests",
        claim_object="Forks",
        evidence_text="I detested Forks",
    )
    assert evidence_offset_in_scene(text, claim) == text.lower().index("i detested")


def test_claim_anchored_requires_evidence_not_object_fallback():
    text = "Edward leaned against the Volvo."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Isabella Swan",
        predicate="loves",
        claim_object="Edward Cullen",
        evidence_text="He loved me openly, trusted me completely.",
        claim_text="Isabella Swan loves Edward Cullen.",
    )
    assert continuity_anchor_in_scene(text, claim)[0] >= 0  # object fallback
    assert claim_anchored_in_scene(text, claim) is False


def test_locate_span_paraphrased_llm_evidence():
    """LLM recall may store a claim sentence; highlight should find the real quote."""
    text = (
        "Charlie was not my father. He was a stranger.\n"
        "I did not trust him at all."
    )
    off, length, anchor = locate_claim_evidence_span(
        text,
        evidence_text="Charlie is not the father of Isabella Swan.",
        claim_text="Charlie is not the father of Isabella Swan.",
    )
    assert off >= 0
    assert length > 0
    assert "charlie was not my father" in anchor.lower()


def test_locate_span_does_not_use_subject_name():
    text = "Isabella Swan arrived. Charlie was not my father."
    off, length, _ = locate_claim_evidence_span(
        text,
        evidence_text="",
        claim_text="The weather remained cloudy all afternoon.",
        claim_object="",
    )
    assert off < 0 and length == 0


def test_multi_sentence_evidence_prefers_relevant_sentence():
    """Long LLM evidence blobs should anchor to the supporting sentence, not a prefix."""
    text = (
        "After two classes, I started to recognize several of the faces in each class. "
        "People asked me questions about how I was liking Forks."
    )
    off, length, anchor = locate_claim_evidence_span(
        text,
        evidence_text=(
            "I started to recognize several of the faces in each class. "
            "People asked me questions about how I was liking Forks."
        ),
        claim_text="Bella is currently living in Forks.",
        claim_object="Forks",
        claim_subject="Bella",
    )
    assert off >= 0
    assert "forks" in anchor.lower()
    assert "recognize" not in anchor.lower()


def test_token_overlap_requires_entity_token():
    text = (
        "After two classes, I started to recognize several of the faces in each class. "
        "People asked me questions about how I was liking Forks."
    )
    off, length, anchor = locate_claim_evidence_span(
        text,
        evidence_text="Bella is currently living in Forks.",
        claim_text="Bella is currently living in Forks.",
        claim_object="Forks",
        claim_subject="Bella",
    )
    assert off >= 0
    assert "forks" in anchor.lower()


def test_short_evidence_expands_to_sentence():
    text = (
        'The door opened and a receptionist greeted me. '
        '"Fine," I lied, my voice weak.'
    )
    off, length, anchor = locate_claim_evidence_span(
        text,
        evidence_text="receptionist",
        claim_text="Isabella Swan lies to the receptionist about her first day.",
        claim_object="receptionist",
        claim_subject="Isabella Swan",
    )
    assert off >= 0
    assert "receptionist" in anchor.lower()
    assert length >= 20
    assert "lied" in anchor.lower() or "greeted" in anchor.lower()


def test_claim_anchored_true_when_evidence_present():
    text = "He loved me openly, trusted me completely. Rain fell."
    claim = Claim(
        story_id=1,
        scene_id=1,
        subject="Isabella Swan",
        predicate="loves",
        claim_object="Edward Cullen",
        evidence_text="He loved me openly, trusted me completely.",
    )
    assert claim_anchored_in_scene(text, claim) is True
