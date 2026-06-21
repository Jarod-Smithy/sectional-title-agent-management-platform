"""Intake Classifier (agent #2) — deterministic, offline triage.

Extracts intent, party, unit, priority and a case reference from an inbound
email. Uses keyword heuristics so the prototype works with zero LLM setup; the
seam is identical to a Haiku-backed classifier.
"""

from __future__ import annotations

import re

from . import config

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
    ("acknowledgement", ["thank you", "thanks", "received", "noted", "acknowledge", "appreciate"]),
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
    import secrets

    prefix = intent[:3].upper() or "GEN"
    unit_part = re.sub(r"\D", "", unit) or "SCH"  # SCH = scheme-wide (no specific unit)
    from .db import now_iso

    stamp = now_iso().replace("-", "").replace(":", "")[2:12]
    suffix = secrets.token_hex(2).upper()  # avoids collisions within the same minute
    return f"{prefix}-{unit_part}-{stamp}-{suffix}"


# --- Task instructions from the chairman ----------------------------------
# The chairman can email the monitored inbox to spawn a board task directly.
# Recognised only when BOTH hold: the sender is a known chairman address AND the
# subject starts with a "TASK:" / "TODO:" prefix. No guardrail screening runs at
# this point — a task is just a reminder; the Governance Guardian screens later
# when the action is actually taken.

_TASK_PREFIX_RE = re.compile(r"^\s*(?:task|todo)\s*[:\-]\s*", re.IGNORECASE)
_DUE_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def is_task_email(sender: str, subject: str) -> bool:
    """True if this inbound email is a chairman task instruction."""
    if sender.strip().lower() not in config.CHAIRMAN_EMAILS:
        return False
    return bool(_TASK_PREFIX_RE.match(subject or ""))


def task_title_from_subject(subject: str) -> str:
    """Strip the TASK:/TODO: prefix, leaving a clean task title."""
    title = _TASK_PREFIX_RE.sub("", subject or "").strip()
    return title or "Untitled task"


def extract_due_date(text: str) -> str:
    """Pull the first ISO date (YYYY-MM-DD) from the text, or '' if none."""
    m = _DUE_DATE_RE.search(text or "")
    return m.group(1) if m else ""
