"""End-to-end API tests against the FastAPI app with an isolated SQLite store."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine"] == "stub"
    assert body["repo_backend"] == "sqlite"


def test_seed_populates_store(client: TestClient) -> None:
    # Lifespan already seeds; an explicit re-seed must be idempotent enough to return counts.
    resp = client.post("/api/seed")
    assert resp.status_code == 200
    counts = resp.json()
    assert counts["documents"] >= 1
    assert counts["resolutions"] >= 1


def test_documents_crud_and_duplicates(client: TestClient) -> None:
    listed = client.get("/api/documents").json()
    assert len(listed) >= 1

    payload = {"title": "Pet Policy", "content": "Owners may keep one small pet."}
    created = client.post("/api/documents", json=payload)
    assert created.status_code == 200
    assert created.json()["title"] == "Pet Policy"

    dup = client.post("/api/documents", json=payload)
    assert dup.status_code == 409

    overwrite = client.post("/api/documents", json={**payload, "overwrite": True})
    assert overwrite.status_code == 200

    empty = client.post("/api/documents", json={"title": "", "content": ""})
    assert empty.status_code == 400


def test_analyze(client: TestClient) -> None:
    resp = client.post(
        "/api/documents/analyze",
        json={
            "content": "Conduct rules: keep common areas tidy at all times.",
            "filename": "rules.txt",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunk_count"] >= 1
    assert body["char_count"] > 0

    blank = client.post("/api/documents/analyze", json={"content": "   "})
    assert blank.status_code == 400


def test_ask(client: TestClient) -> None:
    resp = client.post("/api/ask", json={"question": "What are the garden rules?"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["answer"], str)
    assert isinstance(body["sources"], list)

    blank = client.post("/api/ask", json={"question": "  "})
    assert blank.status_code == 400


def test_inbox_creates_draft(client: TestClient) -> None:
    resp = client.post(
        "/api/inbox",
        json={
            "sender": "jane.doe@example.com",
            "subject": "Leak in Unit 9",
            "body": "There is a water leak in the bathroom of unit 9.",
            "from_unit": "Unit 9",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "draft"
    assert body["draft"]["intent"] == "maintenance"


def test_inbox_creates_task_from_chairman(client: TestClient) -> None:
    resp = client.post(
        "/api/inbox",
        json={
            "sender": "chair@acaciaheights.co.za",
            "subject": "TASK: Obtain three quotes for the gate motor",
            "body": "Please get quotes by 2025-12-01.",
            "from_unit": "",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "task"
    assert "gate motor" in body["ticket"]["title"].lower()


def test_draft_lifecycle_approve_and_block(client: TestClient) -> None:
    drafts = client.get("/api/drafts").json()
    assert drafts

    blocked = [d for d in drafts if any(f["severity"] == "block" for f in d["findings"])]
    clean = [
        d
        for d in drafts
        if d["status"] == "pending" and not any(f["severity"] == "block" for f in d["findings"])
    ]

    if blocked:
        resp = client.post(f"/api/drafts/{blocked[0]['id']}/approve", json=None)
        assert resp.status_code == 409

    if clean:
        draft_id = clean[0]["id"]
        single = client.get(f"/api/drafts/{draft_id}")
        assert single.status_code == 200

        edited = client.put(f"/api/drafts/{draft_id}", json={"body": "Thank you, noted."})
        assert edited.status_code == 200

        approved = client.post(f"/api/drafts/{draft_id}/approve", json=None)
        assert approved.status_code == 200
        assert approved.json()["status"] == "filed"


def test_draft_not_found(client: TestClient) -> None:
    assert client.get("/api/drafts/999999").status_code == 404
    assert client.put("/api/drafts/999999", json={"body": "x"}).status_code == 404
    assert client.post("/api/drafts/999999/approve", json=None).status_code == 404
    assert client.post("/api/drafts/999999/discard").status_code == 404


def test_discard_draft(client: TestClient) -> None:
    pending = [d for d in client.get("/api/drafts").json() if d["status"] == "pending"]
    if pending:
        resp = client.post(f"/api/drafts/{pending[0]['id']}/discard")
        assert resp.status_code == 200
        assert resp.json()["status"] == "discarded"


def test_tickets(client: TestClient) -> None:
    listed = client.get("/api/tickets")
    assert listed.status_code == 200

    created = client.post(
        "/api/tickets",
        json={"title": "Replace lobby light", "type": "maintenance", "priority": "normal"},
    )
    assert created.status_code == 200
    ticket_id = created.json()["id"]

    bad = client.post("/api/tickets", json={"title": "   "})
    assert bad.status_code == 400

    status = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "in_progress"})
    assert status.status_code == 200
    assert status.json()["status"] == "in_progress"

    missing = client.post("/api/tickets/999999/status", json={"status": "done"})
    assert missing.status_code == 404


def test_resolutions(client: TestClient) -> None:
    resp = client.get("/api/resolutions")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_assist_config_toggle(client: TestClient) -> None:
    initial = client.get("/api/assist/config").json()
    assert initial["available"] is True

    updated = client.post(
        "/api/assist/config",
        json={"assist_enabled": True, "kill_switch": True, "available": False},
    )
    assert updated.status_code == 200
    assert updated.json()["available"] is False
