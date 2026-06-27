"""API tests for the SDLC bug-report + feature-request routes.

Uses the default ``client`` fixture (SDLC disabled → offline ``LogIssueTracker``),
overriding wired ports on app state to exercise failure paths. ``sdlc_client``
configures the feature-request approval flow.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pytest
from app.domain.approvals import make_token
from app.ports.email import EmailError
from app.ports.sdlc import IssueRef, IssueTrackerError
from fastapi.testclient import TestClient

_SECRET = "feature-approval-key"  # pragma: allowlist secret


class _RaisingTracker:
    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef:
        raise IssueTrackerError("github down")


class _RaisingEmail:
    def send(self, *, to: str, subject: str, body: str) -> str:
        raise EmailError("ses down")


@pytest.fixture
def sdlc_client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    monkeypatch.setenv("STAK_APPROVER_EMAIL", "approver@example.com")
    monkeypatch.setenv("STAK_APPROVAL_SECRET", _SECRET)
    monkeypatch.setenv("STAK_PUBLIC_BASE_URL", "https://api.example")

    from app.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_report_bug_with_log_tracker_returns_not_created(client: TestClient) -> None:
    resp = client.post(
        "/api/report-bug",
        json={"message": "TypeError: boom", "stack": "at x", "url": "/dash"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is False
    assert data["number"] == 0
    assert data["url"] == "log:not-created"


def test_report_bug_rejects_empty_message(client: TestClient) -> None:
    resp = client.post("/api/report-bug", json={"message": ""})
    assert resp.status_code == 422


def test_report_bug_returns_502_when_tracker_fails(client: TestClient) -> None:
    client.app.state.issue_tracker = _RaisingTracker()  # type: ignore[attr-defined]
    resp = client.post("/api/report-bug", json={"message": "kaboom"})
    assert resp.status_code == 502


# ── Feature request → approval ───────────────────────────────────────────────
def test_feature_request_unconfigured_returns_503(client: TestClient) -> None:
    resp = client.post("/api/feature-request", json={"title": "Dark mode"})
    assert resp.status_code == 503


def test_feature_request_sends_and_acks(sdlc_client: TestClient) -> None:
    resp = sdlc_client.post(
        "/api/feature-request",
        json={"title": "Dark mode", "details": "A theme switch."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["approver"] == "approver@example.com"


def test_feature_request_502_when_email_fails(sdlc_client: TestClient) -> None:
    sdlc_client.app.state.email = _RaisingEmail()  # type: ignore[attr-defined]
    resp = sdlc_client.post("/api/feature-request", json={"title": "Dark mode"})
    assert resp.status_code == 502


def test_approve_valid_token_files_issue(sdlc_client: TestClient) -> None:
    token = make_token(
        secret=_SECRET,
        claims={"title": "Dark mode", "details": "switch", "requester": "dev"},
        ttl_seconds=60,
    )
    resp = sdlc_client.get(f"/api/feature-request/approve?token={token}")
    assert resp.status_code == 200
    assert "approved" in resp.text.lower()


def test_approve_invalid_token_returns_400(sdlc_client: TestClient) -> None:
    resp = sdlc_client.get("/api/feature-request/approve?token=bogus")
    assert resp.status_code == 400


def test_approve_502_when_tracker_fails(sdlc_client: TestClient) -> None:
    sdlc_client.app.state.issue_tracker = _RaisingTracker()  # type: ignore[attr-defined]
    token = make_token(
        secret=_SECRET,
        claims={"title": "x", "details": "", "requester": "dev"},
        ttl_seconds=60,
    )
    resp = sdlc_client.get(f"/api/feature-request/approve?token={token}")
    assert resp.status_code == 502
