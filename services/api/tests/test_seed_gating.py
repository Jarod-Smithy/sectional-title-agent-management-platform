"""Seed-gating tests — demo seeding is gated behind ``STAK_SEED_ENABLED``.

Covers the cold-start auto-seed branch (enabled+empty, enabled+non-empty,
disabled) in ``app.main`` and the ``/api/seed`` route (200 enabled / 403 off).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_autoseed_populates_when_enabled(client: TestClient) -> None:
    # The default ``client`` fixture sets STAK_SEED_ENABLED=true → cold-start
    # seeding ran during lifespan, so the demo corpus is present.
    docs = client.get("/api/documents").json()
    assert len(docs) >= 1
    assert client.get("/api/resolutions").json()


def test_seed_route_reseeds_when_enabled(client: TestClient) -> None:
    resp = client.post("/api/seed")
    assert resp.status_code == 200
    counts = resp.json()
    assert counts["documents"] >= 1
    assert counts["resolutions"] >= 1


def test_autoseed_noop_when_disabled(unseeded_client: TestClient) -> None:
    # Seeding off → cold start leaves the store empty.
    assert unseeded_client.get("/api/documents").json() == []
    assert unseeded_client.get("/api/resolutions").json() == []


def test_seed_route_forbidden_when_disabled(unseeded_client: TestClient) -> None:
    resp = unseeded_client.post("/api/seed")
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


def test_autoseed_skips_when_store_already_populated(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enabled + non-empty store → the cold-start seed is skipped (no reset).

    Exercises the ``repo.count_documents() == 0`` False branch in the lifespan
    by booting a second app against the same already-seeded SQLite store.
    """
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    monkeypatch.setenv("STAK_SEED_ENABLED", "true")

    from app.main import create_app
    from app.settings import get_settings

    get_settings.cache_clear()
    first = create_app()
    with TestClient(first) as c1:
        added = c1.post(
            "/api/documents",
            json={"title": "Marker Doc", "content": "A unique marker document."},
        )
        assert added.status_code == 200
        before = len(c1.get("/api/documents").json())

    # Second boot against the same store: count_documents() != 0 → no re-seed,
    # so the manually-added marker survives (a re-seed would reset the store).
    second = create_app()
    with TestClient(second) as c2:
        docs = c2.get("/api/documents").json()
        assert len(docs) == before
        assert any(d["title"] == "Marker Doc" for d in docs)
    get_settings.cache_clear()
