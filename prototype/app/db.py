"""SQLite store for the prototype.

Maps to the eventual two-store architecture (Vision §4.5):
- documents/doc_chunks  -> Authoritative Knowledge Base (S3 + Bedrock KB)
- interactions          -> Interaction Store (correspondence ledger)
- tickets               -> trustee task board (DynamoDB)
- resolutions           -> resolution register (source of truth)
- drafts                -> pending draft-and-approve queue
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    effective_date TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT NOT NULL DEFAULT '',     -- detected section heading for the chunk
    context TEXT NOT NULL DEFAULT '',     -- contextual prefix used for indexing only
    text TEXT NOT NULL,                   -- clean chunk content shown to the user
    char_start INTEGER NOT NULL DEFAULT 0,
    char_end INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,           -- 'inbound' | 'outbound'
    party TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    case_ref TEXT NOT NULL DEFAULT '',
    topic_key TEXT NOT NULL DEFAULT '',  -- groups the same matter across different email threads
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT NOT NULL DEFAULT 'normal',
    unit TEXT NOT NULL DEFAULT '',
    case_ref TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'email',   -- 'email' | 'chair_email' | 'manual' | 'resolution'
    source_interaction_id INTEGER,
    source_resolution_id INTEGER,
    topic_key TEXT NOT NULL DEFAULT '',     -- links the task to its cross-thread matter
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    effective_date TEXT NOT NULL DEFAULT '',
    signed INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT ''           -- '' = scheme-wide; else the unit it authorises
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    intent TEXT NOT NULL DEFAULT 'general',
    party TEXT NOT NULL DEFAULT '',          -- sender's display name
    from_unit TEXT NOT NULL DEFAULT '',      -- sender's own unit
    unit TEXT NOT NULL DEFAULT '',           -- the unit the matter is ABOUT
    case_ref TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'normal',
    inbound_subject TEXT NOT NULL DEFAULT '',
    inbound_snippet TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'filed' | 'auto_filed' | 'discarded'
    auto_send_eligible INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assist_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'done',     -- 'done' | 'blocked' | 'error'
    complexity TEXT NOT NULL DEFAULT 'simple',
    model_tier TEXT NOT NULL DEFAULT 'fast',
    model TEXT NOT NULL DEFAULT '',
    specialists_json TEXT NOT NULL DEFAULT '[]',  -- roster members the orchestrator engaged
    plan_json TEXT NOT NULL DEFAULT '[]',         -- ordered steps the team executed
    artifacts_json TEXT NOT NULL DEFAULT '[]',    -- typed deliverables produced
    findings_json TEXT NOT NULL DEFAULT '[]',     -- Governance Guardian screen of any actionable output
    capability_gaps_json TEXT NOT NULL DEFAULT '[]',  -- requests outside the capability manifest
    proposed_tool_json TEXT NOT NULL DEFAULT '',  -- draft-PR artifact when a recurring tool should be promoted
    cost_estimate REAL NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with cursor() as cur:
        cur.executescript(_SCHEMA)


def reset_db() -> None:
    with cursor() as cur:
        # Delete child tables before their parents so foreign keys stay satisfied.
        for table in (
            "assist_runs",
            "drafts",
            "tickets",
            "doc_chunks",
            "interactions",
            "documents",
            "resolutions",
        ):
            cur.execute(f"DELETE FROM {table}")  # noqa: S608 — fixed table names
