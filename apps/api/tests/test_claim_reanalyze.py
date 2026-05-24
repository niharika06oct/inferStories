"""Re-analyze must preserve approved claims and merge by source_hash."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_identity import compute_source_hash, source_hash_for_claim_row
from app.database import Base
from app.extraction.persist import (
    delete_replaceable_scene_claims,
    merge_extracted_claims_for_scene,
)
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


def test_compute_source_hash_stable():
    h1 = compute_source_hash("Asha", "relationship_state", "Rohan")
    h2 = compute_source_hash("  asha ", "relationship_state", "rohan")
    assert h1 == h2


def test_reanalyze_preserves_approved(client):
    r = client.post("/stories", json={"title": "Preserve canon"})
    sid = r.json()["id"]
    r = client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan in the hall.",
            "claims": [],
        },
    )
    scene_id = r.json()["id"]
    claims = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    assert len(claims) >= 1
    trust = next(c for c in claims if "trust" in (c.get("claim_text") or "").lower())
    claim_id = trust["id"]

    client.patch(
        f"/stories/{sid}/scenes/{scene_id}/claims/{claim_id}",
        json={"status": "approved"},
    )

    r2 = client.patch(
        f"/stories/{sid}/scenes/{scene_id}",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan in the hall. The rain fell.",
            "claims": [],
            "run_extraction": True,
        },
    )
    assert r2.status_code == 200

    after = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    approved = [c for c in after if c["status"] == "approved"]
    assert any(c["id"] == claim_id for c in approved), (
        "approved claim should survive re-analyze"
    )


def test_merge_updates_same_hash_in_place():
    db = _session()
    try:
        story = Story(title="t", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        h = compute_source_hash("Asha", "relationship_state", "Rohan")
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject="Asha",
            predicate="relationship_state",
            claim_object="Rohan",
            claim_type="relationship_state",
            claim_text="Asha trusts Rohan.",
            status="approved",
            source="extracted",
            source_hash=h,
            claim_version=1,
            confidence=0.95,
        )
        db.add(approved)
        db.flush()
        approved_id = approved.id
        old_version = approved.claim_version

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [
                ExtractedClaim(
                    subject="Asha",
                    claim_type="relationship_state",
                    target="Rohan",
                    claim="Asha trusts Rohan deeply.",
                    confidence=0.92,
                    canon_level="active",
                    evidence="Asha trusts Rohan deeply.",
                    chunk_index=0,
                )
            ],
        )
        db.refresh(approved)

        assert approved.id == approved_id
        assert approved.claim_version == old_version + 1
        assert "deeply" in (approved.claim_text or "")
        assert db.query(Claim).filter(Claim.scene_id == scene.id).count() == 1
    finally:
        db.close()


def test_delete_replaceable_keeps_approved():
    db = _session()
    try:
        story = Story(title="t2", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="A",
                predicate="p",
                claim_object="o",
                status="approved",
                source="extracted",
                source_hash=source_hash_for_claim_row("A", "p", "o", "p"),
            )
        )
        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="B",
                predicate="p",
                claim_object="o",
                status="suggested",
                source="extracted",
                source_hash=source_hash_for_claim_row("B", "p", "o", "p"),
            )
        )
        db.flush()

        delete_replaceable_scene_claims(db, scene)
        remaining = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(remaining) == 1
        assert remaining[0].subject == "A"
    finally:
        db.close()
