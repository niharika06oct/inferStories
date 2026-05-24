"""Manual test flow: approve claims, re-analyze, preserve + version bump."""


def test_full_reanalyze_flow(client):
    r = client.post("/stories", json={"title": "Entity flow"})
    sid = r.json()["id"]
    text_v1 = "Asha trusts Rohan in the hall. Stefan watches the door."
    r = client.post(
        f"/stories/{sid}/scenes",
        json={"scene_number": 1, "text": text_v1, "claims": []},
    )
    scene_id = r.json()["id"]
    claims = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    assert len(claims) >= 1

    trust = next(
        c
        for c in claims
        if "trust" in (c.get("predicate") or "").lower()
        or "trust" in (c.get("claim_text") or "").lower()
    )
    trust_id = trust["id"]
    v0 = trust.get("claim_version", 1)

    client.patch(
        f"/stories/{sid}/scenes/{scene_id}/claims/{trust_id}",
        json={"status": "approved"},
    )

    text_v2 = text_v1 + " Elena glanced at the map on the table."
    client.patch(
        f"/stories/{sid}/scenes/{scene_id}",
        json={
            "scene_number": 1,
            "text": text_v2,
            "claims": [],
            "run_extraction": True,
        },
    )

    after = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    approved = [c for c in after if c["status"] == "approved"]
    suggested = [c for c in after if c["status"] in ("suggested", "needs_review")]

    assert any(c["id"] == trust_id for c in approved), "approved claim survives"
    assert len(suggested) >= 1, "new suggestions after re-analyze"

    trust_after = next(c for c in after if c["id"] == trust_id)
    assert trust_after["claim_version"] == v0 + 1, (
        f"same fact re-found bumps version once (was {v0}, now {trust_after['claim_version']})"
    )



def test_version_only_bumps_on_same_entity_hash(client):
    """Version bumps only when re-extraction matches the same entity source_hash."""
    r = client.post("/stories", json={"title": "Version bump"})
    sid = r.json()["id"]
    client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan.",
            "claims": [
                {
                    "subject": "Old King",
                    "predicate": "ruled",
                    "object": "the North",
                    "claim_type": "timeline_fact",
                }
            ],
        },
    )
    scene_id = client.get(f"/stories/{sid}/scenes").json()[0]["id"]
    claims = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    manual = next(c for c in claims if c["subject"] == "Old King")
    assert manual["status"] == "approved"
    manual_id = manual["id"]
    v0 = manual["claim_version"]

    client.patch(
        f"/stories/{sid}/scenes/{scene_id}",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan deeply.",
            "claims": [],
            "run_extraction": True,
        },
    )
    after = client.get(f"/stories/{sid}/scenes/{scene_id}").json()["claims"]
    manual_after = next(c for c in after if c["id"] == manual_id)
    assert manual_after["claim_version"] == v0

    trust_rows = [
        c
        for c in after
        if "trust" in (c.get("predicate") or "").lower()
        or "trust" in (c.get("claim_text") or "").lower()
    ]
    assert trust_rows, "trust claim still present after re-analyze"
    assert any(c["claim_version"] >= 2 for c in trust_rows)
