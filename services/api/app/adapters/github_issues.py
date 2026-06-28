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
import urllib.parse
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from app.ports.sdlc import IssueRef, IssueTrackerError

logger = logging.getLogger("stak.sdlc")

_GITHUB_API = "https://api.github.com"


class _HttpTransport(Protocol):
    """The two HTTP operations the GitHub adapter needs (GET for dedup search)."""

    def get(self, *, url: str, headers: dict[str, str]) -> tuple[int, bytes]: ...
    def post(self, *, url: str, headers: dict[str, str], payload: bytes) -> tuple[int, bytes]: ...


class UrllibTransport:
    """Minimal stdlib HTTP transport (no third-party dependency)."""

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def get(self, *, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        request = urllib.request.Request(  # noqa: S310 - fixed https GitHub API host
            url, headers=headers, method="GET"
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed https GitHub API host
                request, timeout=self._timeout
            ) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a body
            return int(exc.code), exc.read()

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
        """File a bug/feature issue, de-duplicating against open issues.

        The frontend auto-files a report for EVERY caught UI error, so an
        identical recurring error would otherwise spam a new GitHub issue each
        time. Before creating, we search for an OPEN issue with the EXACT same
        title (titles are a stable function of the error — see
        :func:`app.domain.sdlc.format_bug_report`):

        * Match found → comment a short recurrence note and RETURN the existing
          ``IssueRef``. No duplicate is opened. The route maps ``number > 0`` to
          ``created=true``, so the dashboard still shows a working tracking link
          to the already-open issue (``created`` here means "tracked", not
          "freshly opened").
        * No match (or the search failed for any reason) → create as normal.
          Dedup is best-effort and must NEVER break error reporting.
        """
        existing = self._find_open_issue_by_title(title)
        if existing is not None:
            self._comment_recurrence(existing)
            return existing
        return self._create_issue(title=title, body=body, labels=labels)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "stak-sdlc",
        }

    def _find_open_issue_by_title(self, title: str) -> IssueRef | None:
        """Return an OPEN issue whose title EXACTLY equals ``title``, else None.

        Uses the GitHub Search API; ``in:title`` is FUZZY, so we re-confirm an
        exact, case-sensitive title match on the returned items. Any failure
        (transport error, non-JSON/error body, rate limiting) is swallowed and
        yields ``None`` so a flaky search transparently falls back to creating.
        """
        query = f'repo:{self._repo} is:issue is:open in:title "{title}"'
        url = f"{_GITHUB_API}/search/issues?{urllib.parse.urlencode({'q': query})}"
        try:
            _status, raw = self._transport.get(url=url, headers=self._auth_headers())
            items = json.loads(raw).get("items", [])
            for item in items:
                if item.get("title") == title and item.get("state") == "open":
                    number = item.get("number")
                    html_url = item.get("html_url")
                    if isinstance(number, int) and isinstance(html_url, str):
                        return IssueRef(number=number, url=html_url)
        except Exception:  # defensive: dedup must never break error reporting
            logger.warning("sdlc.dedup.search_failed repo=%s — creating new issue", self._repo)
            return None
        return None

    def _comment_recurrence(self, ref: IssueRef) -> None:
        """Post a best-effort recurrence note; a failure here must not raise."""
        timestamp = datetime.now(UTC).isoformat()
        url = f"{_GITHUB_API}/repos/{self._repo}/issues/{ref.number}/comments"
        payload = json.dumps({"body": f"Recurred at {timestamp}."}).encode("utf-8")
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        try:
            self._transport.post(url=url, headers=headers, payload=payload)
        except Exception:  # best-effort: a failed comment must not break reporting
            logger.warning("sdlc.dedup.comment_failed issue=%d", ref.number)

    def _create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef:
        url = f"{_GITHUB_API}/repos/{self._repo}/issues"
        payload = json.dumps({"title": title, "body": body, "labels": list(labels)}).encode("utf-8")
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
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
