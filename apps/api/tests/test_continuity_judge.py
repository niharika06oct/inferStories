from app.continuity_judge import ContinuityCandidate, judge_continuity_candidate
from app.models import Claim, Scene


def _candidate() -> ContinuityCandidate:
    scene = Scene(story_id=1, scene_number=2, text="b")
    old = Claim(
        story_id=1,
        scene_id=1,
        subject="Bella",
        predicate="trusts",
        claim_object="Charlie",
    )
    new = Claim(
        story_id=1,
        scene_id=2,
        subject="Bella",
        predicate="distrusts",
        claim_object="Charlie",
    )
    return ContinuityCandidate(
        scene=scene,
        new_claim=new,
        old_claim=old,
        severity="medium",
        message="candidate",
        rule_classification="soft_tension",
        rule_reason="Rule reason.",
        conflict_kind="predicate_opposition",
    )


def test_ai_disabled_returns_rule_judgment(monkeypatch):
    monkeypatch.delenv("CONTINUITY_AI_JUDGE_ENABLED", raising=False)
    judgment = judge_continuity_candidate(_candidate())
    assert judgment.source == "rules"
    assert judgment.classification == "soft_tension"


def test_ai_failure_falls_back_to_rule(monkeypatch):
    monkeypatch.setenv("CONTINUITY_AI_JUDGE_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def boom(*_args, **_kwargs):
        raise ValueError("bad json")

    monkeypatch.setattr("app.continuity_judge._ai_judge_continuity_candidate", boom)

    judgment = judge_continuity_candidate(_candidate())
    assert judgment.source == "fallback"
    assert judgment.classification == "soft_tension"
    assert "AI judge failed" in judgment.reason
