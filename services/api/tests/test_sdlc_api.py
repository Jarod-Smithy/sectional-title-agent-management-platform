"""API tests for the SDLC bug-report route.

Uses the default ``client`` fixture (SDLC disabled → offline ``LogIssueTracker``),
overriding the wired tracker on app state to exercise the failure path.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.ports.sdlc import IssueRef, IssueTrackerError
from fastapi.testclient import TestClient


class _RaisingTracker:
    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef:
        raise IssueTrackerError("github down")


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
