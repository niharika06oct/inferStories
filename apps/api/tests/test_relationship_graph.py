"""Relationship graph from approved entity-linked claims."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Claim, Entity, Scene, Story
from app.relationship_graph import build_relationship_graph


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


def test_graph_aggregates_approved_relationships():
    db = _session()
    try:
        story = Story(title="G", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        nahira = Entity(
            story_id=story.id,
            canonical_name="Nahira",
            entity_type="character",
            graph_eligible=True,
            type_confidence=0.9,
        )
        ashan = Entity(
            story_id=story.id,
            canonical_name="Ashan",
            entity_type="character",
            graph_eligible=True,
            type_confidence=0.9,
        )
        db.add_all([nahira, ashan])
        db.flush()

        for pred, conf in (("loves", 0.9), ("desires", 0.85)):
            db.add(
                Claim(
                    story_id=story.id,
                    scene_id=scene.id,
                    subject="Nahira",
                    predicate=pred,
                    claim_object="Ashan",
                    subject_entity_id=nahira.id,
                    object_entity_id=ashan.id,
                    claim_type="relationship_state",
                    claim_text=f"Nahira {pred} Ashan.",
                    status="approved",
                    confidence=conf,
                )
            )
        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="Nahira",
                predicate="distrusts",
                claim_object="Stefan",
                subject_entity_id=nahira.id,
                object_entity_id=None,
                claim_type="relationship_state",
                status="suggested",
                confidence=0.8,
            )
        )
        db.commit()

        graph = build_relationship_graph(db, story.id)
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert edge["primary_relationship"] == "romantic"
        assert set(edge["sub_relationships"]) == {"desires", "loves"}
        assert edge["claim_count"] == 2
        assert edge["predicate"] in ("loves", "romantic")
    finally:
        db.close()


def test_graph_excludes_non_character_love_object():
    db = _session()
    try:
        story = Story(title="Water", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        niharika = Entity(
            story_id=story.id,
            canonical_name="Niharika",
            entity_type="character",
        )
        water = Entity(
            story_id=story.id,
            canonical_name="water",
            entity_type="concept",
        )
        db.add_all([niharika, water])
        db.flush()

        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="Niharika",
                predicate="loves",
                claim_object="water",
                subject_entity_id=niharika.id,
                object_entity_id=water.id,
                claim_type="character_preference",
                claim_text="She still loves the water.",
                status="approved",
                confidence=0.85,
            )
        )
        db.commit()

        graph = build_relationship_graph(db, story.id)
        assert len(graph["edges"]) == 0
        assert all(n["label"] != "water" for n in graph["nodes"])
    finally:
        db.close()


def test_graph_skips_negated_family_relation():
    db = _session()
    try:
        story = Story(title="Neg", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        charlie = Entity(
            story_id=story.id,
            canonical_name="Charlie",
            entity_type="character",
            graph_eligible=True,
        )
        bella = Entity(
            story_id=story.id,
            canonical_name="Bella",
            entity_type="character",
            graph_eligible=True,
        )
        db.add_all([charlie, bella])
        db.flush()

        db.add(
            Claim(
                story_id=story.id,
                scene_id=scene.id,
                subject="Charlie",
                predicate="father_of",
                claim_object="Bella",
                subject_entity_id=charlie.id,
                object_entity_id=bella.id,
                claim_type="relationship_state",
                claim_text="Charlie was not Bella's father.",
                polarity=False,
                status="approved",
                confidence=0.9,
            )
        )
        db.commit()

        graph = build_relationship_graph(db, story.id)
        assert graph["edges"] == []
        assert graph["meta"]["approved_relationship_claim_count"] == 0
    finally:
        db.close()


def test_graph_skips_negated_trust_but_keeps_positive():
    db = _session()
    try:
        story = Story(title="Trust", description=None, owner_user_id="u")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.id, scene_number=1, text="x")
        db.add(scene)
        db.flush()

        asha = Entity(
            story_id=story.id,
            canonical_name="Asha",
            entity_type="character",
            graph_eligible=True,
        )
        rohan = Entity(
            story_id=story.id,
            canonical_name="Rohan",
            entity_type="character",
            graph_eligible=True,
        )
        stefan = Entity(
            story_id=story.id,
            canonical_name="Stefan",
            entity_type="character",
            graph_eligible=True,
        )
        db.add_all([asha, rohan, stefan])
        db.flush()

        db.add_all(
            [
                Claim(
                    story_id=story.id,
                    scene_id=scene.id,
                    subject="Asha",
                    predicate="trusts",
                    claim_object="Rohan",
                    subject_entity_id=asha.id,
                    object_entity_id=rohan.id,
                    claim_type="relationship_state",
                    polarity=True,
                    status="approved",
                    confidence=0.9,
                ),
                Claim(
                    story_id=story.id,
                    scene_id=scene.id,
                    subject="Asha",
                    predicate="trusts",
                    claim_object="Stefan",
                    subject_entity_id=asha.id,
                    object_entity_id=stefan.id,
                    claim_type="relationship_state",
                    polarity=False,
                    claim_text="Asha did not trust Stefan.",
                    status="approved",
                    confidence=0.85,
                ),
            ]
        )
        db.commit()

        graph = build_relationship_graph(db, story.id)
        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert edge["target_entity_id"] == rohan.id
        assert edge["sub_relationships"] == ["trusts"]
        assert edge["supporting_claims"][0]["polarity"] is True
    finally:
        db.close()


def test_graph_endpoint(client):
    r = client.post("/stories", json={"title": "Graph API"})
    sid = r.json()["id"]
    client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan.",
            "claims": [],
        },
    )
    scene_id = client.get(f"/stories/{sid}/scenes").json()[0]["id"]
    claims = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    trust = next(c for c in claims if "trust" in (c.get("predicate") or "").lower())
    client.patch(
        f"/stories/{sid}/scenes/{scene_id}/claims/{trust['id']}",
        json={"status": "approved"},
    )
    g = client.get(f"/stories/{sid}/relationship-graph")
    assert g.status_code == 200
    body = g.json()
    assert body["story_id"] == sid
    assert len(body["nodes"]) >= 2
    assert len(body["edges"]) >= 1
