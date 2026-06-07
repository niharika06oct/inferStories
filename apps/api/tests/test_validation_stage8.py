"""FASTUS Stage 8 — polarity-aware validation and superseded-claim skipping."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Claim, Scene, Story
from app.validation import ValidationStats, validate_scene_claims


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


def test_negated_trust_aligns_with_prior_distrust_no_double_issue():
    """trusts+polarity=false is stance-equivalent to distrusts — not a soft tension."""
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
                predicate="distrusts",
                claim_object="Stefan",
                polarity=True,
                status="approved",
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
            claim_object="Stefan",
            polarity=False,
            status="approved",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert issues == []
    finally:
        db.close()


def test_superseded_claim_does_not_trigger_exclusive_object_conflict():
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
                polarity=True,
                status="approved",
                valid_until_scene=s1.id,
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
            polarity=True,
            is_major_plotline=True,
            status="approved",
        )
        db.add(c_new)
        db.flush()

        stats = ValidationStats()
        issues = validate_scene_claims(db, s2, [c_new], validation_stats=stats)
        assert issues == []
        assert stats.superseded_skipped >= 1
    finally:
        db.close()


def test_open_prior_still_triggers_exclusive_object_conflict():
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
                polarity=True,
                status="approved",
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
            polarity=True,
            is_major_plotline=True,
            status="approved",
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].judge_classification == "hard_contradiction"
    finally:
        db.close()


def test_validation_stats_records_polarity_flip():
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
                subject="Charlie",
                predicate="father_of",
                claim_object="Bella",
                polarity=True,
                status="approved",
            )
        )

        s2 = Scene(story_id=story.id, scene_number=2, text="b")
        db.add(s2)
        db.flush()
        c_new = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Charlie",
            predicate="father_of",
            claim_object="Bella",
            polarity=False,
            status="approved",
        )
        db.add(c_new)
        db.flush()

        stats = ValidationStats()
        issues = validate_scene_claims(db, s2, [c_new], validation_stats=stats)
        assert len(issues) == 1
        assert stats.polarity_flips == 1
        assert any(ev["event"] == "polarity_flip" for ev in stats.events)
    finally:
        db.close()
