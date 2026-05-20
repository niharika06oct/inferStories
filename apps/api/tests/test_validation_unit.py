"""Direct checks on validate_scene_claims (contradiction rule)."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
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


def test_non_major_medium_severity():
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
        assert len(issues) == 1
        assert issues[0].severity == "medium"
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
            claim_object="Nobody",
            is_major_plotline=False,
        )
        db.add(c_new)
        db.flush()

        issues = validate_scene_claims(db, s2, [c_new])
        assert len(issues) == 1
        assert issues[0].severity == "medium"
    finally:
        db.close()
