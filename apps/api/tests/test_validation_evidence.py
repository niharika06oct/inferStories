from app.models import Claim
from app.validation_evidence import (
    claim_anchored_in_scene,
    continuity_anchor_in_scene,
    evidence_offset_in_scene,
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
