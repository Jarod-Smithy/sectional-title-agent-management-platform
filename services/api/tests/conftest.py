"""Shared pytest fixtures — a TestClient backed by an isolated temp SQLite store."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    # The dashboard test-suite asserts against the seeded "Acacia Heights" demo,
    # so the default client opts in (mirrors the dev live stack). The disabled
    # branch is exercised by ``unseeded_client``.
    monkeypatch.setenv("STAK_SEED_ENABLED", "true")

    from app.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def unseeded_client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client with demo seeding OFF (``STAK_SEED_ENABLED`` unset → default False).

    Exercises the cold-start no-seed branch and the disabled ``/api/seed`` (403).
    """
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    monkeypatch.delenv("STAK_SEED_ENABLED", raising=False)

    from app.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
