"""Unit tests for the issue-tracker adapters + the SDLC composition root.

No network: ``GitHubIssueTracker`` takes an INJECTED HTTP transport, and
``UrllibTransport`` is exercised by monkeypatching ``urllib.request.urlopen``.
"""

from __future__ import annotations

import json
import logging
import urllib.error
from io import BytesIO
from typing import Any

import pytest
from app.adapters.github_issues import (
    GitHubIssueTracker,
    LogIssueTracker,
    UrllibTransport,
)
from app.bootstrap import build_issue_tracker
from app.ports.sdlc import IssueTrackerError
from app.settings import Settings


class _FakeTransport:
    """Programmable GitHub HTTP double exercising the adapter's REAL URL-building
    and JSON parsing — no network, no mocking of the adapter itself.

    Each endpoint (search GET, create POST, comment POST) has canned responses;
    every request (method + url + body) is recorded for assertions.
    """

    def __init__(
        self,
        *,
        search_items: list[dict[str, Any]] | None = None,
        search_status: int = 200,
        search_raises: bool = False,
        create_status: int = 201,
        create_body: bytes = b'{"number": 7, "html_url": "https://gh/7"}',
        create_raises: bool = False,
        comment_status: int = 201,
        comment_raises: bool = False,
    ) -> None:
        self._search_items = search_items or []
        self._search_status = search_status
        self._search_raises = search_raises
        self._create_status = create_status
        self._create_body = create_body
        self._create_raises = create_raises
        self._comment_status = comment_status
        self._comment_raises = comment_raises
        self.requests: list[dict[str, Any]] = []

    def get(self, *, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.requests.append({"method": "GET", "url": url, "payload": None})
        if self._search_raises:
            raise RuntimeError("search unavailable")
        return self._search_status, json.dumps({"items": self._search_items}).encode("utf-8")

    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]:
        self.requests.append({"method": "POST", "url": url, "payload": payload})
        if url.endswith("/comments"):
            if self._comment_raises:
                raise RuntimeError("comment unavailable")
            return self._comment_status, b"{}"
        if self._create_raises:
            raise RuntimeError("connection reset")
        return self._create_status, self._create_body

    def creates(self) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["method"] == "POST" and r["url"].endswith("/issues")]

    def comments(self) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["url"].endswith("/comments")]


# ── LogIssueTracker (dev no-op) ──────────────────────────────────────────────
def test_log_tracker_records_but_never_calls(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracker = LogIssueTracker()
    with caplog.at_level(logging.INFO, logger="stak.sdlc"):
        ref = tracker.create_issue(title="t", body="b", labels=["ai-sdlc", "bug"])
    assert ref.number == 0
    assert ref.url == "log:not-created"
    assert "ai-sdlc" in caplog.text


# ── GitHubIssueTracker ───────────────────────────────────────────────────────
def test_github_tracker_requires_owner_name_repo() -> None:
    with pytest.raises(IssueTrackerError):
        GitHubIssueTracker(transport=_FakeTransport(), repo="noslash", token="t")


def test_github_tracker_requires_token() -> None:
    with pytest.raises(IssueTrackerError):
        GitHubIssueTracker(transport=_FakeTransport(), repo="o/r", token="")


def test_github_tracker_creates_issue_and_parses_response() -> None:
    # Search returns no items → the adapter creates a new issue.
    transport = _FakeTransport(
        search_items=[], create_body=b'{"number": 7, "html_url": "https://gh/7"}'
    )
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["ai-sdlc", "bug"])
    assert ref.number == 7
    assert ref.url == "https://gh/7"
    assert len(transport.creates()) == 1
    assert not transport.comments()
    created = transport.creates()[0]
    assert created["url"].endswith("/repos/o/r/issues")
    assert json.loads(created["payload"])["labels"] == ["ai-sdlc", "bug"]
    search = transport.requests[0]
    assert search["method"] == "GET"
    assert "/search/issues" in search["url"]
    assert search["url"].endswith("in%3Atitle+%22Bug%22")


def test_github_tracker_dedupes_to_existing_open_issue() -> None:
    # Search returns an OPEN issue with the SAME title → comment, no create.
    existing = {
        "number": 11,
        "title": "Bug",
        "state": "open",
        "html_url": "https://gh/11",
    }
    transport = _FakeTransport(search_items=[existing])
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["ai-sdlc", "bug"])
    assert ref.number == 11
    assert ref.url == "https://gh/11"
    assert not transport.creates()
    assert len(transport.comments()) == 1
    comment = transport.comments()[0]
    assert comment["url"].endswith("/repos/o/r/issues/11/comments")
    assert "Recurred at" in json.loads(comment["payload"])["body"]


def test_github_tracker_ignores_fuzzy_non_exact_title_and_creates() -> None:
    # GitHub search is fuzzy: a near-miss title must NOT be treated as a match.
    noise = {
        "number": 5,
        "title": "Bug in something else",
        "state": "open",
        "html_url": "https://gh/5",
    }
    transport = _FakeTransport(search_items=[noise])
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["bug"])
    assert ref.number == 7  # the default create response
    assert len(transport.creates()) == 1


def test_github_tracker_creates_when_matched_item_is_malformed() -> None:
    # Exact title+state match, but an unusable number/url → not a valid ref, so
    # the adapter must fall back to creating rather than dedup to garbage.
    bad = {"number": "x", "title": "Bug", "state": "open", "html_url": None}
    transport = _FakeTransport(search_items=[bad])
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["bug"])
    assert ref.number == 7
    assert len(transport.creates()) == 1


def test_github_tracker_falls_back_to_create_when_search_fails() -> None:
    # Defensive branch: a failing dedup search must NOT block error reporting.
    transport = _FakeTransport(search_raises=True)
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["bug"])
    assert ref.number == 7
    assert len(transport.creates()) == 1


def test_github_tracker_dedupe_comment_failure_still_returns_existing() -> None:
    # A failed recurrence comment is best-effort and must not raise / create.
    existing = {
        "number": 11,
        "title": "Bug",
        "state": "open",
        "html_url": "https://gh/11",
    }
    transport = _FakeTransport(search_items=[existing], comment_raises=True)
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["bug"])
    assert ref.number == 11
    assert not transport.creates()
    assert len(transport.comments()) == 1


def test_github_tracker_raises_on_non_201() -> None:
    tracker = GitHubIssueTracker(
        transport=_FakeTransport(create_status=422, create_body=b'{"message": "Validation"}'),
        repo="o/r",
        token="tok",
    )
    with pytest.raises(IssueTrackerError):
        tracker.create_issue(title="t", body="b", labels=["bug"])


def test_github_tracker_raises_on_unexpected_payload() -> None:
    tracker = GitHubIssueTracker(
        transport=_FakeTransport(create_body=b'{"number": "nope"}'),
        repo="o/r",
        token="tok",
    )
    with pytest.raises(IssueTrackerError):
        tracker.create_issue(title="t", body="b", labels=["bug"])


def test_github_tracker_wraps_transport_failure() -> None:
    tracker = GitHubIssueTracker(
        transport=_FakeTransport(create_raises=True), repo="o/r", token="tok"
    )
    with pytest.raises(IssueTrackerError):
        tracker.create_issue(title="t", body="b", labels=["bug"])


# ── UrllibTransport (stdlib) ─────────────────────────────────────────────────
class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_urllib_transport_returns_status_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        return _FakeResponse(201, b'{"number": 1, "html_url": "u"}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status, body = UrllibTransport().post(url="https://x", headers={}, payload=b"{}")
    assert status == 201
    assert b"html_url" in body


def test_urllib_transport_get_returns_status_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        return _FakeResponse(200, b'{"items": []}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status, body = UrllibTransport().get(url="https://x", headers={})
    assert status == 200
    assert b"items" in body


def test_urllib_transport_get_returns_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(
            url="https://x",
            code=403,
            msg="Forbidden",
            hdrs=None,  # type: ignore[arg-type]
            fp=BytesIO(b'{"message": "rate limited"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status, body = UrllibTransport().get(url="https://x", headers={})
    assert status == 403
    assert b"rate limited" in body


def test_urllib_transport_returns_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(
            url="https://x",
            code=422,
            msg="Unprocessable",
            hdrs=None,  # type: ignore[arg-type]
            fp=BytesIO(b'{"message": "Validation failed"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status, body = UrllibTransport().post(url="https://x", headers={}, payload=b"{}")
    assert status == 422
    assert b"Validation failed" in body


# ── Composition root ─────────────────────────────────────────────────────────
def test_build_issue_tracker_defaults_to_log() -> None:
    tracker = build_issue_tracker(Settings(sdlc_enabled=False))
    assert isinstance(tracker, LogIssueTracker)


def test_build_issue_tracker_wires_github_with_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSecrets:
        def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
            assert SecretId == "stak/sdlc/github-pat"  # pragma: allowlist secret
            return {"SecretString": "fake-pat-value\n"}  # pragma: allowlist secret

    monkeypatch.setattr("boto3.client", lambda *a, **k: _FakeSecrets())
    tracker = build_issue_tracker(Settings(sdlc_enabled=True, github_repo="owner/repo"))
    assert isinstance(tracker, GitHubIssueTracker)
