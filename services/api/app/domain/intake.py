"""Intake Classifier — deterministic, offline triage (ported from the prototype).

Pure functions: extract intent, party, unit, priority and a case reference from
an inbound email. The seam is identical to a Haiku-backed classifier.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime

_INTENT_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "maintenance",
        [
            "leak",
            "broken",
            "repair",
            "fix",
            "geyser",
            "plumbing",
            "electrical",
            "lift",
            "gate motor",
            "pool",
            "garden",
            "maintenance",
            "damage",
            "blocked drain",
        ],
    ),
    (
        "complaint",
        [
            "complaint",
            "noise",
            "nuisance",
            "parking",
            "pet",
            "dog",
            "unhappy",
            "disturb",
            "rude",
            "smell",
        ],
    ),
    (
        "financial",
        [
            "levy",
            "levies",
            "payment",
            "arrears",
            "account",
            "statement",
            "invoice",
            "refund",
            "balance",
            "interest",
            "owe",
        ],
    ),
    (
        "governance",
        [
            "agm",
            "sgm",
            "meeting",
            "trustee",
            "election",
            "resolution",
            "vote",
            "quorum",
            "minutes",
            "agenda",
        ],
    ),
    (
        "compliance",
        [
            "insurance",
            "coc",
            "fire",
            "compliance",
            "regulation",
            "by-law",
            "bylaw",
            "rules",
            "fica",
        ],
    ),
    (
        "acknowledgement",
        ["thank you", "thanks", "received", "noted", "acknowledge", "appreciate"],
    ),
]

_UNIT_RE = re.compile(r"\bunit\s*(\d+[a-z]?)\b", re.IGNORECASE)
_PRIORITY_HIGH = [
    "urgent",
    "emergency",
    "immediately",
    "asap",
    "flooding",
    "no water",
    "no electricity",
    "danger",
    "fire",
]
_TASK_PREFIX_RE = re.compile(r"^\s*(?:task|todo)\s*[:\-]\s*", re.IGNORECASE)
_DUE_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def classify_intent(subject: str, body: str) -> str:
    text = f"{subject}\n{body}".lower()
    scores: dict[str, int] = {}
    for intent, words in _INTENT_KEYWORDS:
        hits = sum(1 for w in words if w in text)
        if hits:
            scores[intent] = hits
    if not scores:
        return "general"
    return max(scores, key=lambda k: scores[k])


def extract_party(sender: str) -> str:
    name = sender.split("@", 1)[0]
    name = re.sub(r"[._]+", " ", name).strip()
    return name.title() or sender


def extract_unit(subject: str, body: str) -> str:
    m = _UNIT_RE.search(f"{subject} {body}")
    return f"Unit {m.group(1)}" if m else ""


def priority(subject: str, body: str) -> str:
    text = f"{subject} {body}".lower()
    return "high" if any(w in text for w in _PRIORITY_HIGH) else "normal"


def case_ref(intent: str, unit: str) -> str:
    prefix = intent[:3].upper() or "GEN"
    unit_part = re.sub(r"\D", "", unit) or "SCH"  # SCH = scheme-wide
    stamp = datetime.now(UTC).isoformat(timespec="seconds").replace("-", "").replace(":", "")[2:12]
    suffix = secrets.token_hex(2).upper()
    return f"{prefix}-{unit_part}-{stamp}-{suffix}"


def is_task_email(sender: str, subject: str, chairman_emails: Iterable[str]) -> bool:
    """True if this inbound email is a chairman task instruction."""
    if sender.strip().lower() not in {e.lower() for e in chairman_emails}:
        return False
    return bool(_TASK_PREFIX_RE.match(subject or ""))


def task_title_from_subject(subject: str) -> str:
    title = _TASK_PREFIX_RE.sub("", subject or "").strip()
    return title or "Untitled task"


def extract_due_date(text: str) -> str:
    m = _DUE_DATE_RE.search(text or "")
    return m.group(1) if m else ""
