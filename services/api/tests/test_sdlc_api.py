"""API tests for the SDLC bug-report + feature-request routes.

Uses the default ``client`` fixture (SDLC disabled → offline ``LogIssueTracker``),
overriding wired ports on app state to exercise failure paths. ``sdlc_client``
configures the feature-request approval flow.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from app.adapters.github_issues import GitHubIssueTracker
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


class _StatefulGitHubTransport:
    """In-memory GitHub HTTP double used through the REAL ``GitHubIssueTracker``.

    ``create`` stores an open issue; ``search`` returns every open issue (GitHub
    search is fuzzy — the adapter confirms the exact title match), so the SAME
    error reported twice de-dupes to one issue. Records every request.
    """

    def __init__(self) -> None:
        self._open: list[dict[str, Any]] = []
        self._next = 1
        self.requests: list[dict[str, Any]] = []

    def get(self, *, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.requests.append({"method": "GET", "url": url, "payload": None})
        return 200, json.dumps({"items": self._open}).encode("utf-8")

    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]:
        self.requests.append({"method": "POST", "url": url, "payload": payload})
        if url.endswith("/comments"):
            return 201, b"{}"
        number = self._next
        self._next += 1
        issue = {
            "number": number,
            "title": json.loads(payload)["title"],
            "state": "open",
            "html_url": f"https://gh/{number}",
        }
        self._open.append(issue)
        return 201, json.dumps({"number": number, "html_url": issue["html_url"]}).encode("utf-8")

    def creates(self) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["method"] == "POST" and r["url"].endswith("/issues")]

    def comments(self) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["url"].endswith("/comments")]


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


def test_report_bug_twice_dedupes_to_single_github_issue(client: TestClient) -> None:
    # Wire the REAL GitHub adapter onto a stateful in-memory transport, then
    # report the SAME error twice: the second call must reuse the first issue.
    transport = _StatefulGitHubTransport()
    client.app.state.issue_tracker = GitHubIssueTracker(  # type: ignore[attr-defined]
        transport=transport,
        repo="o/r",
        token="tok",  # pragma: allowlist secret
    )
    payload = {"message": "TypeError: boom", "stack": "at x:1", "url": "/dash"}

    first = client.post("/api/report-bug", json=payload)
    second = client.post("/api/report-bug", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    for resp in (first, second):
        data = resp.json()
        assert data["created"] is True
        assert data["url"].startswith("https://gh/")
    # Exactly one issue was created; the recurrence was filed as a comment.
    assert len(transport.creates()) == 1
    assert len(transport.comments()) == 1
    assert first.json()["url"] == second.json()["url"]


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
