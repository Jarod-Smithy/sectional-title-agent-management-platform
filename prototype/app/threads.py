"""Cross-thread topic consolidation.

Owners often raise the same matter across *different* email threads — a fresh
"New email" here, a "Re: Re: Fwd:" there — so a single issue gets scattered.
This module assigns every interaction a stable ``topic_key`` by fuzzy-matching
new mail against existing mail on three signals:

* **Subject similarity** — after stripping ``Re:``/``Fwd:`` noise (Jaccard).
* **Participant** — same party / unit.
* **Content similarity** — overlap of the message bodies (Jaccard).

Matches above a threshold inherit the existing topic's key; otherwise a new key
is minted. Tasks carry the topic_key of their originating mail so the board can
show "related threads" and the agent can reason over the whole matter at once.

In production this is the AgentCore **Memory** store keyed by topic; here it is
a deterministic, stdlib-only computation over the SQLite ``interactions`` table.
"""

from __future__ import annotations

import re
import secrets

from . import db, rag

_PREFIX_RE = re.compile(r"^\s*(re|fwd|fw|aw|wg)\s*:\s*", re.I)
_NONWORD_RE = re.compile(r"[^a-z0-9]+")

# Weighting of the three similarity signals (sum = 1.0).
_W_SUBJECT = 0.5
_W_CONTENT = 0.3
_W_PARTY = 0.2

# A new interaction joins an existing topic when the best blended score clears
# this bar. Tuned so "Re: leak" and "Water coming through ceiling, unit 12"
# from the same owner consolidate, while unrelated mail stays separate.
_MATCH_THRESHOLD = 0.42


def normalize_subject(subject: str) -> str:
    """Strip repeated Re:/Fwd: prefixes and punctuation; lowercase."""
    s = subject or ""
    while True:
        stripped = _PREFIX_RE.sub("", s)
        if stripped == s:
            break
        s = stripped
    s = _NONWORD_RE.sub(" ", s.lower()).strip()
    return s


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _subject_tokens(subject: str) -> set[str]:
    return set(normalize_subject(subject).split())


def _content_tokens(body: str) -> set[str]:
    return set(rag.tokenize(body or ""))


def _party_match(a_party: str, a_unit: str, b_party: str, b_unit: str) -> float:
    score = 0.0
    if a_party and b_party and a_party.strip().lower() == b_party.strip().lower():
        score += 0.6
    if a_unit and b_unit and a_unit.strip().lower() == b_unit.strip().lower():
        score += 0.4
    return min(score, 1.0)


def similarity(
    a_subject: str,
    a_body: str,
    a_party: str,
    a_unit: str,
    b_subject: str,
    b_body: str,
    b_party: str,
    b_unit: str,
) -> float:
    subj = _jaccard(_subject_tokens(a_subject), _subject_tokens(b_subject))
    content = _jaccard(_content_tokens(a_body), _content_tokens(b_body))
    party = _party_match(a_party, a_unit, b_party, b_unit)
    return _W_SUBJECT * subj + _W_CONTENT * content + _W_PARTY * party


def _mint_key(subject: str) -> str:
    slug = normalize_subject(subject).replace(" ", "-")[:28].strip("-")
    return f"{slug or 'topic'}-{secrets.token_hex(3)}"


def assign_topic_key(subject: str, body: str, party: str, unit: str) -> str:
    """Return the topic_key this message belongs to — reusing an existing
    topic's key when it is similar enough, else minting a new one."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT subject, body, party, unit, topic_key FROM interactions "
            "WHERE topic_key != '' ORDER BY id DESC LIMIT 300"
        )
        rows = cur.fetchall()

    best_key = ""
    best_score = 0.0
    for r in rows:
        score = similarity(
            subject,
            body,
            party,
            unit,
            r["subject"],
            r["body"],
            r["party"],
            r["unit"],
        )
        if score > best_score:
            best_score = score
            best_key = r["topic_key"]

    if best_key and best_score >= _MATCH_THRESHOLD:
        return best_key
    return _mint_key(subject)


def related_threads(topic_key: str, *, exclude_id: int | None = None) -> list[dict]:
    """All interactions sharing a topic_key — the consolidated matter view."""
    if not topic_key:
        return []
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, direction, party, subject, unit, case_ref, created_at "
            "FROM interactions WHERE topic_key = ? ORDER BY created_at",
            (topic_key,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        if exclude_id is not None and r["id"] == exclude_id:
            continue
        out.append(dict(r))
    return out


def topic_key_for_text(subject: str, body: str = "", party: str = "", unit: str = "") -> str:
    """Best-match topic_key for free text (e.g. a manually-created task) without
    minting a new key — returns '' when nothing related exists."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT subject, body, party, unit, topic_key FROM interactions "
            "WHERE topic_key != '' ORDER BY id DESC LIMIT 300"
        )
        rows = cur.fetchall()
    best_key, best_score = "", 0.0
    for r in rows:
        score = similarity(
            subject,
            body,
            party,
            unit,
            r["subject"],
            r["body"],
            r["party"],
            r["unit"],
        )
        if score > best_score:
            best_score, best_key = score, r["topic_key"]
    return best_key if best_score >= _MATCH_THRESHOLD else ""
