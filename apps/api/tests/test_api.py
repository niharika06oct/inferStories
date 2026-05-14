def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_contradiction_flow(client):
    r = client.post(
        "/stories",
        json={"title": "The Ashen Oath", "description": "Fantasy"},
    )
    assert r.status_code == 200
    story_id = r.json()["id"]

    r = client.post(
        f"/stories/{story_id}/scenes",
        json={
            "scene_number": 1,
            "text": "Asha trusts Rohan.",
            "claims": [
                {
                    "subject": "Asha",
                    "predicate": "trusts",
                    "object": "Rohan",
                    "is_major_plotline": True,
                }
            ],
        },
    )
    assert r.status_code == 200

    r = client.post(
        f"/stories/{story_id}/scenes",
        json={
            "scene_number": 2,
            "text": "Asha does not trust Rohan.",
            "claims": [
                {
                    "subject": "Asha",
                    "predicate": "trusts",
                    "object": "Nobody",
                    "is_major_plotline": True,
                }
            ],
        },
    )
    assert r.status_code == 200

    r = client.post(f"/stories/{story_id}/validate")
    assert r.status_code == 200
    issues = r.json()
    assert len(issues) >= 1
    assert issues[0]["severity"] == "high"
    assert "major" in issues[0]["message"].lower()
    assert issues[0]["story_id"] == story_id
    assert "created_at" in issues[0]


def test_duplicate_scene_number_returns_409(client):
    r = client.post("/stories", json={"title": "Dup test"})
    sid = r.json()["id"]
    body = {
        "scene_number": 1,
        "text": "first",
        "claims": [
            {"subject": "A", "predicate": "p", "object": "o", "is_major_plotline": False}
        ],
    }
    assert client.post(f"/stories/{sid}/scenes", json=body).status_code == 200
    r2 = client.post(f"/stories/{sid}/scenes", json=body)
    assert r2.status_code == 409
