"""
Pre-merge verification (manual checklist encoded as tests).

1. Jon / Jon Snow / I resolve when POV = Jon Snow
2. Re-analyze does not duplicate entities
3. Predicates are semantic verbs, not claim_type slugs
"""

from app.entity_registry import (
    _CLAIM_TYPE_SLUGS,
    ensure_pov_entity,
    find_entity_by_name,
    get_or_create_entity,
)
from app.models import Entity


def test_pov_jon_snow_resolves_jon_jon_snow_and_i(client):
  sid = client.post("/stories", json={"title": "POV resolution"}).json()["id"]
  text = (
      "I distrusts Stefan. Jon distrusts the Wildlings. "
      "Jon Snow looked north."
  )
  client.post(
      f"/stories/{sid}/scenes",
      json={
          "scene_number": 1,
          "text": text,
          "pov_character": "Jon Snow",
          "claims": [],
      },
  )
  entities = client.get(f"/stories/{sid}/entities").json()
  jon_rows = [e for e in entities if "jon" in e["canonical_name"].lower()]
  assert len(jon_rows) == 1, f"expected one Jon entity, got {jon_rows}"
  ent = jon_rows[0]
  assert ent["canonical_name"] == "Jon Snow"
  alias_keys = {a.lower() for a in ent["aliases"]}
  assert "i" in alias_keys
  assert "me" in alias_keys

  scene = client.get(f"/stories/{sid}/scenes").json()[0]
  claims = client.get(f"/stories/{sid}/scenes/{scene['id']}").json()["claims"]
  jon_claims = [c for c in claims if c.get("subject_entity_id") == ent["id"]]
  assert len(jon_claims) >= 2, "I and Jon should attach to the same Jon Snow entity"
  subjects = {c["subject"] for c in jon_claims}
  assert "Jon Snow" in subjects
  assert any(s in ("Jon", "Jon Snow") for s in subjects)

  alias_keys_after = {a.lower() for a in ent["aliases"]}
  assert "jon" in alias_keys_after, (
      "surface form Jon should be stored as alias after extraction"
  )


def test_reanalyze_does_not_duplicate_entities(client):
  sid = client.post("/stories", json={"title": "No dup entities"}).json()["id"]
  text_v1 = "Jon Snow trusts Sam. Jon glanced at the fire."
  r = client.post(
      f"/stories/{sid}/scenes",
      json={
          "scene_number": 1,
          "text": text_v1,
          "pov_character": "Jon Snow",
          "claims": [],
      },
  )
  scene_id = r.json()["id"]
  n1 = len(client.get(f"/stories/{sid}/entities").json())

  client.patch(
      f"/stories/{sid}/scenes/{scene_id}",
      json={
          "scene_number": 1,
          "text": text_v1 + " The wind rose.",
          "pov_character": "Jon Snow",
          "claims": [],
          "run_extraction": True,
      },
  )
  n2 = len(client.get(f"/stories/{sid}/entities").json())
  assert n2 == n1, f"entity count grew from {n1} to {n2} on re-analyze"

  jon_entities = [
      e
      for e in client.get(f"/stories/{sid}/entities").json()
      if e["canonical_name"].lower().startswith("jon")
  ]
  assert len(jon_entities) == 1


def test_predicates_are_semantic_not_claim_type(client):
  sid = client.post("/stories", json={"title": "Semantic predicates"}).json()["id"]
  client.post(
      f"/stories/{sid}/scenes",
      json={
          "scene_number": 1,
          "text": (
              "Asha trusts Rohan. Nahira distrusts Stefan. "
              "Bran is the half-brother of Jon Snow."
          ),
          "claims": [],
      },
  )
  scene_id = client.get(f"/stories/{sid}/scenes").json()[0]["id"]
  claims = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
  assert claims, "expected extracted claims"

  for c in claims:
      pred = (c.get("predicate") or "").strip().lower()
      assert pred not in _CLAIM_TYPE_SLUGS, (
          f"predicate must not be claim_type slug, got {pred!r} on claim {c['id']}"
      )
      assert pred, "predicate should be non-empty"

  preds = {c["predicate"].lower() for c in claims}
  assert "trusts" in preds or any("trust" in p for p in preds)
  assert "distrusts" in preds or any("distrust" in p for p in preds)
  assert "is_half_brother_of" in preds
