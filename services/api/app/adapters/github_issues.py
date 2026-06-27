"""Issue-tracker adapters — the offline ``log`` no-op and the GitHub REST sender.

Both implement :class:`app.ports.sdlc.IssueTracker`. The composition root
(:mod:`app.bootstrap`) selects one from ``STAK_SDLC_ENABLED``; the domain only
ever sees the Protocol.

Design notes (mirrors the email/S3 adapters):
* ``LogIssueTracker`` performs NO network I/O — it logs and returns a synthetic
  ``IssueRef(number=0, …)``. It is the dev/CI default so the suite never calls
  GitHub.
* ``GitHubIssueTracker`` takes an INJECTED HTTP transport (a tiny Protocol), so
  the parsing/validation logic is unit-testable with no network. The real
  ``UrllibTransport`` (stdlib ``urllib``) is built only when the SDLC pipeline
  is enabled.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Protocol

from app.ports.sdlc import IssueRef, IssueTrackerError

logger = logging.getLogger("stak.sdlc")

_GITHUB_API = "https://api.github.com"


class _HttpTransport(Protocol):
    """The single HTTP operation the GitHub adapter needs."""

    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]: ...


class UrllibTransport:
    """Minimal stdlib HTTP POST transport (no third-party dependency)."""

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]:
        request = urllib.request.Request(  # noqa: S310 - fixed https GitHub API host
            url, data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed https GitHub API host
                request, timeout=self._timeout
            ) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a body
            return int(exc.code), exc.read()


class LogIssueTracker:
    """Dev-safe no-op tracker: records the would-be issue and never calls out."""

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef:
        logger.info(
            "sdlc.issue.log title=%s labels=%s chars=%d (not created — log tracker)",
            title,
            ",".join(labels),
            len(body),
        )
        return IssueRef(number=0, url="log:not-created")


class GitHubIssueTracker:
    """Files issues against a GitHub repository via the REST API."""

    def __init__(self, *, transport: _HttpTransport, repo: str, token: str) -> None:
        if not repo or "/" not in repo:
            raise IssueTrackerError("github repo must be in 'owner/name' form.")
        if not token:
            raise IssueTrackerError("github token is required when SDLC is enabled.")
        self._transport = transport
        self._repo = repo
        self._token = token

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef:
        url = f"{_GITHUB_API}/repos/{self._repo}/issues"
        payload = json.dumps({"title": title, "body": body, "labels": list(labels)}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "stak-sdlc",
        }
        try:
            status, raw = self._transport.post(url=url, headers=headers, payload=payload)
        except Exception as exc:  # network / transport failure
            raise IssueTrackerError(f"GitHub issue create failed: {exc}") from exc
        if status != 201:
            detail = raw.decode("utf-8", errors="replace")[:200]
            raise IssueTrackerError(f"GitHub issue create returned HTTP {status}: {detail}")
        data = json.loads(raw)
        number = data.get("number")
        html_url = data.get("html_url")
        if not isinstance(number, int) or not isinstance(html_url, str):
            raise IssueTrackerError("GitHub issue create returned an unexpected payload.")
        return IssueRef(number=number, url=html_url)
