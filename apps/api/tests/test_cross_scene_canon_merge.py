"""Cross-chapter merge: accepted story memory suppresses duplicate review prompts."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_entities import resolve_extracted
from app.database import Base
from app.extraction.persist import merge_extracted_claims_for_scene
from app.extraction.schema import ExtractedClaim
from app.models import Claim, Scene, Story


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


def _mother_claim(*, evidence: str, confidence: float = 0.78) -> ExtractedClaim:
    return ExtractedClaim(
        subject="Renée",
        claim_type="relationship_state",
        predicate="mother_of",
        target="Isabella Swan",
        claim="Renée is the mother of Isabella Swan.",
        polarity=True,
        confidence=confidence,
        canon_level="active",
        evidence=evidence,
        chunk_index=0,
        generation_origin="family",
    )


def test_later_chapter_skips_duplicate_mother_claim_when_already_approved():
    db = _session()
    try:
        story = Story(title="Twilight", description=None, owner_user_id="u")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Renée was my mother.")
        s2 = Scene(
            story_id=story.id,
            scene_number=13,
            text="My mom had never missed me.",
        )
        db.add_all([s1, s2])
        db.flush()

        resolved = resolve_extracted(db, story.id, _mother_claim(evidence="Renée was my mother."))
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject=resolved.subject,
                predicate=resolved.predicate,
                claim_object=resolved.claim_object,
                polarity=True,
                subject_entity_id=resolved.subject_entity_id,
                object_entity_id=resolved.object_entity_id,
                claim_type=resolved.claim_type,
                claim_text="Renée is the mother of Isabella Swan.",
                evidence_text="Renée was my mother.",
                status="approved",
                source="extracted",
                source_hash=resolved.source_hash,
                claim_version=1,
                confidence=0.9,
            )
        )
        db.flush()

        merge_extracted_claims_for_scene(
            db,
            s2,
            [_mother_claim(evidence="My mom")],
        )
        db.flush()

        rows = db.query(Claim).filter(Claim.scene_id == s2.id).all()
        assert rows == []
    finally:
        db.close()


def test_changed_polarity_still_inserts_for_review():
    db = _session()
    try:
        story = Story(title="Neg", description=None, owner_user_id="u")
        db.add(story)
        db.flush()

        s1 = Scene(story_id=story.id, scene_number=1, text="Charlie is my father.")
        s2 = Scene(story_id=story.id, scene_number=13, text="Charlie was not my father.")
        db.add_all([s1, s2])
        db.flush()

        pos = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Charlie",
                claim_type="relationship_state",
                predicate="father_of",
                target="Isabella Swan",
                claim="Charlie is the father of Isabella Swan.",
                polarity=True,
                confidence=0.9,
                evidence="Charlie is my father.",
                chunk_index=0,
            ),
        )
        db.add(
            Claim(
                story_id=story.id,
                scene_id=s1.id,
                subject=pos.subject,
                predicate=pos.predicate,
                claim_object=pos.claim_object,
                polarity=True,
                subject_entity_id=pos.subject_entity_id,
                object_entity_id=pos.object_entity_id,
                claim_type=pos.claim_type,
                status="approved",
                source="extracted",
                source_hash=pos.source_hash,
                claim_version=1,
            )
        )
        db.flush()

        neg = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Charlie",
                claim_type="relationship_state",
                predicate="father_of",
                target="Isabella Swan",
                claim="Charlie is not the father of Isabella Swan.",
                polarity=False,
                confidence=0.85,
                evidence="Charlie was not my father.",
                chunk_index=0,
            ),
        )
        merge_extracted_claims_for_scene(
            db,
            s2,
            [
                ExtractedClaim(
                    subject="Charlie",
                    claim_type="relationship_state",
                    predicate="father_of",
                    target="Isabella Swan",
                    claim="Charlie is not the father of Isabella Swan.",
                    polarity=False,
                    confidence=0.85,
                    evidence="Charlie was not my father.",
                    chunk_index=0,
                )
            ],
        )
        db.flush()

        rows = db.query(Claim).filter(Claim.scene_id == s2.id).all()
        assert len(rows) == 1
        assert rows[0].polarity is False
        assert rows[0].status in ("suggested", "needs_review", "approved")
    finally:
        db.close()


def test_first_chapter_still_creates_review_claim():
    db = _session()
    try:
        story = Story(title="First", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="My mom")
        db.add(scene)
        db.flush()

        merge_extracted_claims_for_scene(db, scene, [_mother_claim(evidence="My mom")])
        db.flush()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(rows) == 1
        assert rows[0].status in ("suggested", "needs_review")
    finally:
        db.close()
