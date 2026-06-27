"""SDLC port — the single seam to the issue tracker (GitHub).

The AI-native SDLC pipeline turns runtime signals (captured errors, feature
requests) into labelled issues that downstream automation acts on. Domain code
depends on this Protocol; ``LogIssueTracker`` (dev default) is an offline no-op
and ``GitHubIssueTracker`` files real issues via the GitHub REST API.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class IssueTrackerError(RuntimeError):
    """Raised when issue creation fails or returns an unusable response."""


@dataclass(frozen=True)
class IssueRef:
    """A created issue. ``number == 0`` marks the offline log no-op."""

    number: int
    url: str


class IssueTracker(Protocol):
    """Create a tracker issue and return a reference to it."""

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRef: ...
