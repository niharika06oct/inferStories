"""Re-analyze removes claims (and continuity issues) no longer supported by chapter text."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Claim, Scene, Story, ValidationIssue
from app.scene_service import save_scene_with_extraction


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


def test_reanalyze_drops_stale_approved_claim_and_clears_continuity_issue():
    db = _session()
    try:
        story = Story(title="Twilight", description=None, owner_user_id="u")
        db.add(story)
        db.flush()

        s1 = Scene(
            story_id=story.id,
            scene_number=12,
            text="I couldn't suppress the worry that I was responsible for his absence.",
        )
        db.add(s1)
        db.flush()
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject="Isabella Swan",
                predicate="distrusts",
                claim_object="Edward Cullen",
                evidence_text=(
                    "I couldn't totally suppress the worry that I was responsible "
                    "for his continued absence"
                ),
                status="approved",
                source="extracted",
                is_major_plotline=True,
            )
        )

        loves_text = "He loved me openly, trusted me completely."
        s2 = Scene(
            story_id=story.id,
            scene_number=13,
            text=f"{loves_text} Edward leaned against the Volvo.",
        )
        db.add(s2)
        db.flush()
        loves = Claim(
            story_id=story.id,
            scene_id=s2.id,
            subject="Isabella Swan",
            predicate="loves",
            claim_object="Edward Cullen",
            evidence_text=loves_text,
            claim_text="Isabella Swan loves Edward Cullen.",
            status="approved",
            source="extracted",
            is_major_plotline=True,
        )
        db.add(loves)
        db.flush()

        save_scene_with_extraction(db, s2, manual_claims=[], run_extraction=False)
        db.flush()
        assert (
            db.query(ValidationIssue)
            .filter(ValidationIssue.scene_id == s2.id)
            .count()
            == 1
        )

        s2.text = "Edward leaned against the Volvo. I drove away."
        save_scene_with_extraction(db, s2, manual_claims=[], run_extraction=False)
        db.flush()

        remaining = (
            db.query(Claim)
            .filter(Claim.scene_id == s2.id, Claim.predicate == "loves")
            .all()
        )
        assert remaining == []
        assert (
            db.query(ValidationIssue)
            .filter(ValidationIssue.scene_id == s2.id)
            .count()
            == 0
        )
    finally:
        db.close()


def test_reanalyze_keeps_approved_claim_when_evidence_still_in_text():
    db = _session()
    try:
        story = Story(title="Keep", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(
            story_id=story.id,
            scene_number=1,
            text="Asha trusts Rohan in the hall.",
        )
        db.add(scene)
        db.flush()
        trust = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject="Asha",
            predicate="trusts",
            claim_object="Rohan",
            evidence_text="Asha trusts Rohan in the hall.",
            status="approved",
            source="extracted",
        )
        db.add(trust)
        db.flush()

        scene.text = "Asha trusts Rohan in the hall. The rain fell."
        save_scene_with_extraction(db, scene, manual_claims=[], run_extraction=False)
        db.flush()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert any(r.predicate == "trusts" and r.status == "approved" for r in rows)
    finally:
        db.close()
