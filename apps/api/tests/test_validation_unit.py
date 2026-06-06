"""Direct checks on validate_scene_claims (contradiction rule)."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.continuity_judge import ContinuityJudgment
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


def test_major_plotline_sets_high_severity():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Asha",
                predicate="trusts",
                claim_object="Rohan",
                is_major_plotline=True,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Asha",
            predicate="trusts",
            claim_object="Nobody",
            is_major_plotline=True,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].severity == "high"
    finally:
        db.close()


def test_same_predicate_non_exclusive_object_is_not_conflict():
    db = _session()
    try:
        story = Story(title="t2", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="A",
                predicate="likes",
                claim_object="B",
                is_major_plotline=False,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="A",
            predicate="likes",
            claim_object="C",
            is_major_plotline=False,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert issues == []
    finally:
        db.close()


def test_same_subject_and_object_different_predicate_is_conflict():
    """e.g. 'running towards X' vs 'running away from X' — same subject+object, different verb."""
    db = _session()
    try:
        story = Story(title="t3", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Nahira",
                predicate="Running towards",
                claim_object="Ashan",
                is_major_plotline=True,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Nahira",
            predicate="running away from",
            claim_object="Ashan",
            is_major_plotline=False,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].severity == "high"
        assert "Ashan" in issues[0].message
        assert "Running towards" in issues[0].message or "towards" in issues[0].message.lower()
    finally:
        db.close()


def test_subject_predicate_normalized_for_object_rule():
    db = _session()
    try:
        story = Story(title="t4", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="  Asha ",
                predicate="trusts",
                claim_object="Rohan",
                is_major_plotline=False,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="asha",
            predicate="trusts",
            claim_object="Edward",
            is_major_plotline=False,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert issues == []
    finally:
        db.close()


def test_suggested_current_claim_checked_against_past_canon():
    db = _session()
    try:
        story = Story(title="suggested", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        pending = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="trusts",
            claim_object="Edward",
            status="suggested",
        )
        db.add(pending)
        db.flush()

        issues = validate_scene_claims(db, s2, [pending])
        assert issues == []
    finally:
        db.close()


def test_needs_review_current_claim_checked_against_past_canon():
    db = _session()
    try:
        story = Story(title="review", description=None, owner_user_id="test-user")
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
                predicate="loves",
                claim_object="Phoenix",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        pending = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="loves",
            claim_object="Forks",
            status="needs_review",
        )
        db.add(pending)
        db.flush()

        issues = validate_scene_claims(db, s2, [pending])
        assert issues == []
    finally:
        db.close()


def test_rejected_current_claim_not_checked():
    db = _session()
    try:
        story = Story(title="rejected", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        rejected = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="trusts",
            claim_object="Edward",
            status="rejected",
        )
        db.add(rejected)
        db.flush()

        issues = validate_scene_claims(db, s2, [rejected])
        assert issues == []
    finally:
        db.close()


def test_past_suggested_claim_not_used_as_canon():
    db = _session()
    try:
        story = Story(title="past-pending", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
                status="suggested",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="trusts",
            claim_object="Edward",
            status="suggested",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_exclusive_object_predicate_still_conflicts():
    db = _session()
    try:
        story = Story(title="exclusive", description=None, owner_user_id="test-user")
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
        assert "Phoenix" in issues[0].message
        assert "Forks" in issues[0].message
    finally:
        db.close()


def test_negative_emotional_stance_progression_is_not_conflict():
    db = _session()
    try:
        story = Story(title="stance", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="a")
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Isabella Swan",
                predicate="distrusts",
                claim_object="Edward Cullen",
                status="approved",
                is_major_plotline=True,
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Isabella Swan",
            predicate="dreads",
            claim_object="Edward Cullen",
            status="suggested",
            is_major_plotline=True,
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_positive_negative_same_pair_is_soft_conflict():
    db = _session()
    try:
        story = Story(title="opposite", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Edward",
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
            predicate="distrusts",
            claim_object="Edward",
            status="suggested",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert len(issues) == 1
        assert issues[0].severity == "medium"
        assert "earlier 'trusts', now 'distrusts'" in issues[0].message
        assert issues[0].judge_source == "rules"
        assert issues[0].judge_classification == "soft_tension"
        assert issues[0].judge_reason
    finally:
        db.close()


def test_ai_judgment_can_suppress_rule_candidate(monkeypatch):
    db = _session()
    try:
        story = Story(title="ai-suppress", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
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
            predicate="distrusts",
            claim_object="Charlie",
            status="suggested",
            evidence_text="It made me hesitate, but I still asked Charlie.",
        )
        db.add(current)
        db.flush()

        def fake_judge(_candidate):
            return ContinuityJudgment(
                classification="not_issue",
                confidence=0.93,
                reason="AI judged this as mild hesitation, not contradiction.",
                source="ai",
            )

        monkeypatch.setattr("app.validation.judge_continuity_candidate", fake_judge)

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_ai_hard_contradiction_judgment_metadata_saved(monkeypatch):
    db = _session()
    try:
        story = Story(title="ai-show", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
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
            predicate="distrusts",
            claim_object="Charlie",
            status="suggested",
            evidence_text="I didn't trust Charlie with the secret.",
        )
        db.add(current)
        db.flush()

        def fake_judge(_candidate):
            return ContinuityJudgment(
                classification="hard_contradiction",
                confidence=0.88,
                reason="The later evidence explicitly reverses trust.",
                source="ai",
            )

        monkeypatch.setattr("app.validation.judge_continuity_candidate", fake_judge)

        issues = validate_scene_claims(db, s2, [current])
        assert len(issues) == 1
        assert issues[0].judge_source == "ai"
        assert issues[0].judge_classification == "hard_contradiction"
        assert issues[0].judge_confidence == 0.88
        assert "explicitly reverses trust" in (issues[0].judge_reason or "")
    finally:
        db.close()


def test_uncomfortable_evidence_is_not_distrust_conflict():
    db = _session()
    try:
        story = Story(title="uncomfortable", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
                status="approved",
                is_major_plotline=True,
                evidence_text="One of the best things about Charlie is he doesn't hover.",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        current = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Bella",
            predicate="distrusts",
            claim_object="Charlie",
            status="suggested",
            is_major_plotline=True,
            evidence_text="It made me uncomfortable.",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert issues == []
    finally:
        db.close()


def test_explicit_distrust_evidence_still_conflicts_with_trust():
    db = _session()
    try:
        story = Story(title="explicit-distrust", description=None, owner_user_id="test-user")
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
                predicate="trusts",
                claim_object="Charlie",
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
            predicate="distrusts",
            claim_object="Charlie",
            status="suggested",
            evidence_text="I didn't trust Charlie with the secret.",
        )
        db.add(current)
        db.flush()

        issues = validate_scene_claims(db, s2, [current])
        assert len(issues) == 1
    finally:
        db.close()
