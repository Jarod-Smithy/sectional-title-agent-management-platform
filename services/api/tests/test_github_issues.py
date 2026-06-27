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
    """Stands in for the HTTP transport the GitHub adapter posts through."""

    def __init__(
        self, *, status: int = 201, body: bytes | None = None, raises: bool = False
    ) -> None:
        self._status = status
        self._body = body if body is not None else b'{"number": 42, "html_url": "u"}'
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]:
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        if self._raises:
            raise RuntimeError("connection reset")
        return self._status, self._body


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
    transport = _FakeTransport(body=b'{"number": 7, "html_url": "https://gh/7"}')
    tracker = GitHubIssueTracker(transport=transport, repo="o/r", token="tok")
    ref = tracker.create_issue(title="Bug", body="Body", labels=["ai-sdlc", "bug"])
    assert ref.number == 7
    assert ref.url == "https://gh/7"
    sent = transport.calls[0]
    assert sent["url"].endswith("/repos/o/r/issues")
    assert sent["headers"]["Authorization"] == "Bearer tok"
    assert json.loads(sent["payload"])["labels"] == ["ai-sdlc", "bug"]


def test_github_tracker_raises_on_non_201() -> None:
    tracker = GitHubIssueTracker(
        transport=_FakeTransport(status=422, body=b'{"message": "Validation"}'),
        repo="o/r",
        token="tok",
    )
    with pytest.raises(IssueTrackerError):
        tracker.create_issue(title="t", body="b", labels=["bug"])


def test_github_tracker_raises_on_unexpected_payload() -> None:
    tracker = GitHubIssueTracker(
        transport=_FakeTransport(body=b'{"number": "nope"}'),
        repo="o/r",
        token="tok",
    )
    with pytest.raises(IssueTrackerError):
        tracker.create_issue(title="t", body="b", labels=["bug"])


def test_github_tracker_wraps_transport_failure() -> None:
    tracker = GitHubIssueTracker(transport=_FakeTransport(raises=True), repo="o/r", token="tok")
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
