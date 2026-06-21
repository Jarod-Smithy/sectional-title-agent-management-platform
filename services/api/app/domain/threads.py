"""Thread consolidation — group correspondence about the same matter.

The prototype performed fuzzy cross-thread matching against the interaction
ledger. This port keeps a deterministic, dependency-free topic key (normalised
subject + unit) so the same matter lands under one key even when the email
subject gains ``Re:`` / ``Fwd:`` prefixes. Full similarity-based matching is a
later enhancement once the repository exposes the ledger for scanning.
"""

from __future__ import annotations

import re

_PREFIX_RE = re.compile(r"^\s*(?:re|fwd|fw|aw|wg)\s*[:\-]\s*", re.IGNORECASE)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_subject(subject: str) -> str:
    """Strip reply/forward prefixes (repeatedly) and normalise whitespace."""
    text = subject or ""
    while True:
        stripped = _PREFIX_RE.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return text.strip().lower()


def topic_key_for_text(subject: str, body: str, party: str, unit: str) -> str:
    """Deterministic key grouping the same matter across email threads."""
    base = normalize_subject(subject)
    if not base:
        # Fall back to the first words of the body so subject-less mail still groups.
        base = " ".join((body or "").strip().lower().split()[:6])
    slug = _NON_WORD.sub("-", base).strip("-")[:60] or "general"
    unit_part = _NON_WORD.sub("", (unit or "").lower()) or "scheme"
    return f"{unit_part}:{slug}"
