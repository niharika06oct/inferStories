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


def test_list_stories_and_scenes(client):
    r = client.post("/stories", json={"title": "Alpha"})
    sid = r.json()["id"]
    client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Opening.",
            "claims": [
                {
                    "subject": "A",
                    "predicate": "p",
                    "object": "o",
                    "is_major_plotline": False,
                }
            ],
        },
    )

    stories = client.get("/stories")
    assert stories.status_code == 200
    items = stories.json()
    assert any(s["id"] == sid and s["title"] == "Alpha" and s["scene_count"] == 1 for s in items)

    detail = client.get(f"/stories/{sid}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Alpha"

    scenes = client.get(f"/stories/{sid}/scenes")
    assert scenes.status_code == 200
    assert len(scenes.json()) == 1
    scene_id = scenes.json()[0]["id"]

    full = client.get(f"/stories/{sid}/scenes/{scene_id}")
    assert full.status_code == 200
    assert full.json()["text"] == "Opening."
    assert len(full.json()["claims"]) == 1


def test_update_story_and_generate_description(client):
    r = client.post("/stories", json={"title": "Synopsis test"})
    sid = r.json()["id"]
    client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "A knight enters the foggy village.",
            "claims": [],
        },
    )
    r = client.patch(
        f"/stories/{sid}",
        json={"title": "Renamed", "description": "A foggy tale."},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    assert r.json()["description"] == "A foggy tale."

    r = client.post(f"/stories/{sid}/generate-description")
    assert r.status_code == 200
    body = r.json()
    assert body["description"]
    assert body["source"] in ("openai", "heuristic")

    r = client.get(f"/stories/{sid}")
    assert r.json()["description"] == body["description"]


def test_generate_description_requires_scenes(client):
    r = client.post("/stories", json={"title": "Empty"})
    sid = r.json()["id"]
    r = client.post(f"/stories/{sid}/generate-description")
    assert r.status_code == 400


def test_scene_with_empty_claims(client):
    r = client.post("/stories", json={"title": "Import draft"})
    sid = r.json()["id"]
    r = client.post(
        f"/stories/{sid}/scenes",
        json={"scene_number": 1, "text": "Imported prose only.", "claims": []},
    )
    assert r.status_code == 200


def test_update_scene(client):
    r = client.post("/stories", json={"title": "Edit me"})
    sid = r.json()["id"]
    r = client.post(
        f"/stories/{sid}/scenes",
        json={
            "scene_number": 1,
            "text": "Draft.",
            "claims": [
                {
                    "subject": "A",
                    "predicate": "p",
                    "object": "o",
                    "is_major_plotline": False,
                }
            ],
        },
    )
    scene_id = r.json()["id"]
    r = client.patch(
        f"/stories/{sid}/scenes/{scene_id}",
        json={
            "scene_number": 1,
            "text": "Revised prose.",
            "claims": [
                {
                    "subject": "A",
                    "predicate": "p",
                    "object": "x",
                    "is_major_plotline": True,
                }
            ],
        },
    )
    assert r.status_code == 200
    full = client.get(f"/stories/{sid}/scenes/{scene_id}")
    assert full.json()["text"] == "Revised prose."
    assert full.json()["claims"][0]["object"] == "x"
    assert full.json()["claims"][0]["is_major_plotline"] is True


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
