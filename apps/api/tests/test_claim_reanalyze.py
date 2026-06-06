"""Re-analyze must preserve approved claims and merge by source_hash."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.claim_entities import resolve_extracted
from app.claim_identity import (
    compute_entity_source_hash,
    compute_source_hash,
    source_hash_for_claim_row,
)
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

        resolved = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Asha",
                claim_type="relationship_state",
                predicate="trusts",
                target="Rohan",
                claim="Asha trusts Rohan.",
                confidence=0.95,
                canon_level="active",
                evidence="Asha trusts Rohan.",
                chunk_index=0,
            ),
        )
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=resolved.subject,
            predicate=resolved.predicate,
            claim_object=resolved.claim_object,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            claim_type=resolved.claim_type,
            claim_text="Asha trusts Rohan.",
            status="approved",
            source="extracted",
            source_hash=resolved.source_hash,
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
                    predicate="trusts",
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


def test_merge_matches_approved_by_evidence_when_hash_differs():
    """Re-extract with refined claim_type must not duplicate an approved row."""
    db = _session()
    try:
        story = Story(title="t3", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        first = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Niharika",
                claim_type="relationship_state",
                predicate="loves",
                target="water",
                claim="Niharika loves the water.",
                confidence=0.62,
                canon_level="soft",
                evidence="I loved Niharika",
                chunk_index=0,
            ),
        )
        approved = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=first.subject,
            predicate=first.predicate,
            claim_object=first.claim_object,
            subject_entity_id=first.subject_entity_id,
            object_entity_id=first.object_entity_id,
            claim_type="relationship_state",
            claim_text="Niharika has a strong emotional stance toward water.",
            status="approved",
            source="extracted",
            # Legacy hash from before claim_type refinement on approve.
            source_hash=compute_entity_source_hash(
                first.subject_entity_id,
                first.predicate,
                first.object_entity_id,
                "relationship_state",
            ),
            evidence_text="I loved Niharika",
            claim_version=1,
            confidence=0.62,
        )
        db.add(approved)
        db.flush()

        second = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Niharika",
                claim_type="relationship_state",
                predicate="loves",
                target="water",
                claim="Niharika loves the water.",
                confidence=0.62,
                canon_level="soft",
                evidence="I loved Niharika",
                chunk_index=0,
            ),
        )
        assert second.claim_type == "character_preference"
        assert second.source_hash != approved.source_hash

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [
                ExtractedClaim(
                    subject="Niharika",
                    claim_type="relationship_state",
                    predicate="loves",
                    target="water",
                    claim="Niharika loves the water.",
                    confidence=0.62,
                    canon_level="soft",
                    evidence="I loved Niharika",
                    chunk_index=0,
                )
            ],
        )
        db.commit()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(rows) == 1
        assert rows[0].status == "approved"
        assert rows[0].claim_type == "character_preference"
    finally:
        db.close()


def test_rejected_not_resurfaced_as_suggested():
    db = _session()
    try:
        story = Story(title="rej", description=None, owner_user_id="test-user")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        resolved = resolve_extracted(
            db,
            story.id,
            ExtractedClaim(
                subject="Asha",
                claim_type="relationship_state",
                predicate="trusts",
                target="Rohan",
                claim="Asha trusts Rohan.",
                confidence=0.58,
                canon_level="soft",
                evidence="Asha trusts Rohan in the hall.",
                chunk_index=0,
            ),
        )
        rejected = Claim(
            story_id=story.id,
            scene_id=scene.id,
            subject=resolved.subject,
            predicate=resolved.predicate,
            claim_object=resolved.claim_object,
            subject_entity_id=resolved.subject_entity_id,
            object_entity_id=resolved.object_entity_id,
            claim_type=resolved.claim_type,
            claim_text="Asha trusts Rohan.",
            status="rejected",
            source="extracted",
            source_hash=resolved.source_hash,
            evidence_text="Asha trusts Rohan in the hall.",
            claim_version=1,
            confidence=0.58,
        )
        db.add(rejected)
        db.flush()
        rejected_id = rejected.id

        delete_replaceable_scene_claims(db, scene)
        merge_extracted_claims_for_scene(
            db,
            scene,
            [
                ExtractedClaim(
                    subject="Asha",
                    claim_type="relationship_state",
                    predicate="trusts",
                    target="Rohan",
                    claim="Asha trusts Rohan.",
                    confidence=0.6,
                    canon_level="soft",
                    evidence="Asha trusts Rohan in the hall.",
                    chunk_index=0,
                )
            ],
        )
        db.commit()

        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(rows) == 1
        assert rows[0].id == rejected_id
        assert rows[0].status == "rejected"
        assert rows[0].confidence == 0.6
    finally:
        db.close()


def test_delete_replaceable_keeps_approved_and_rejected():
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
        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="C",
                predicate="p",
                claim_object="o",
                status="rejected",
                source="extracted",
                source_hash=source_hash_for_claim_row("C", "p", "o", "p"),
            )
        )
        db.flush()

        delete_replaceable_scene_claims(db, scene)
        remaining = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        assert len(remaining) == 2
        subjects = {r.subject for r in remaining}
        assert subjects == {"A", "C"}
    finally:
        db.close()
