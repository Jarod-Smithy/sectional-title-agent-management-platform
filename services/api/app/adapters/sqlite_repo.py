"""SQLite implementation of the :class:`app.ports.repository.Repository` port.

Local-dev / CI persistence. Maps rows ↔ pydantic schemas. The same method
surface is implemented by the DynamoDB adapter for production (Increment 6), so
no domain code changes.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.ports.repository import Chunk, CorpusItem
from app.schemas import (
    Document,
    Draft,
    GuardrailFinding,
    Resolution,
    Source,
    Ticket,
)

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
    heading TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL DEFAULT 0,
    char_end INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,
    party TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    case_ref TEXT NOT NULL DEFAULT '',
    topic_key TEXT NOT NULL DEFAULT '',
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
    source TEXT NOT NULL DEFAULT 'email',
    source_interaction_id INTEGER,
    source_resolution_id INTEGER,
    topic_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    effective_date TEXT NOT NULL DEFAULT '',
    signed INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    intent TEXT NOT NULL DEFAULT 'general',
    party TEXT NOT NULL DEFAULT '',
    from_unit TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    case_ref TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'normal',
    inbound_subject TEXT NOT NULL DEFAULT '',
    inbound_snippet TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    auto_send_eligible INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SqliteRepository:
    """File-backed (or in-memory) SQLite store implementing the Repository port."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        finally:
            conn.close()

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def init(self) -> None:
        with self._cursor() as cur:
            cur.executescript(_SCHEMA)

    def reset(self) -> None:
        with self._cursor() as cur:
            for table in (
                "drafts",
                "tickets",
                "doc_chunks",
                "interactions",
                "documents",
                "resolutions",
            ):
                cur.execute(f"DELETE FROM {table}")  # noqa: S608 — fixed names

    # ── Documents + corpus ───────────────────────────────────────────────────
    def add_document(
        self,
        *,
        title: str,
        content: str,
        category: str,
        effective_date: str,
        chunks: list[Chunk],
    ) -> Document:
        created = _now_iso()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO documents (title, category, effective_date, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, category, effective_date, content, created),
            )
            doc_id = int(cur.lastrowid or 0)
            for ch in chunks:
                cur.execute(
                    "INSERT INTO doc_chunks "
                    "(doc_id, ordinal, heading, context, text, char_start, char_end) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        ch.ordinal,
                        ch.heading,
                        ch.context,
                        ch.text,
                        ch.char_start,
                        ch.char_end,
                    ),
                )
        return Document(
            id=doc_id,
            title=title,
            category=category,
            effective_date=effective_date,
            created_at=created,
        )

    def get_document_by_title(self, title: str) -> Document | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, title, category, effective_date, created_at "
                "FROM documents WHERE title = ?",
                (title,),
            )
            row = cur.fetchone()
        return _to_document(row) if row else None

    def delete_document_by_title(self, title: str) -> bool:
        with self._cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE title = ?", (title,))
            row = cur.fetchone()
            if row is None:
                return False
            cur.execute("DELETE FROM documents WHERE id = ?", (int(row["id"]),))
        return True

    def list_documents(self) -> list[Document]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, title, category, effective_date, created_at "
                "FROM documents ORDER BY id DESC"
            )
            rows = cur.fetchall()
        return [_to_document(r) for r in rows]

    def count_documents(self) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM documents")
            row = cur.fetchone()
        return int(row["n"])

    def corpus(self, *, interaction_limit: int = 200) -> list[CorpusItem]:
        items: list[CorpusItem] = []
        with self._cursor() as cur:
            cur.execute(
                "SELECT c.context AS context, c.text AS text, d.title AS title "
                "FROM doc_chunks c JOIN documents d ON d.id = c.doc_id"
            )
            for row in cur.fetchall():
                items.append(
                    CorpusItem(
                        title=str(row["title"]),
                        snippet=str(row["text"]),
                        index_text=f"{row['context']} {row['text']}",
                        kind="document",
                    )
                )
            cur.execute(
                "SELECT subject, body, party, direction FROM interactions "
                "ORDER BY id DESC LIMIT ?",
                (interaction_limit,),
            )
            for row in cur.fetchall():
                blob = f"{row['subject']} {row['body']}"
                items.append(
                    CorpusItem(
                        title=f"{row['direction']} · {row['party']} · {row['subject']}",
                        snippet=blob,
                        index_text=blob,
                        kind="interaction",
                    )
                )
        return items

    # ── Interactions ─────────────────────────────────────────────────────────
    def add_interaction(
        self,
        *,
        direction: str,
        party: str,
        subject: str,
        body: str,
        unit: str,
        case_ref: str,
        topic_key: str = "",
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO interactions "
                "(direction, party, subject, body, unit, case_ref, topic_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (direction, party, subject, body, unit, case_ref, topic_key, _now_iso()),
            )
            return int(cur.lastrowid or 0)

    # ── Drafts ───────────────────────────────────────────────────────────────
    def add_draft(
        self,
        *,
        interaction_id: int,
        intent: str,
        party: str,
        from_unit: str,
        unit: str,
        case_ref: str,
        priority: str,
        inbound_subject: str,
        inbound_snippet: str,
        body: str,
        auto_send_eligible: bool,
        findings: list[GuardrailFinding],
        sources: list[Source],
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO drafts "
                "(interaction_id, intent, party, from_unit, unit, case_ref, priority, "
                " inbound_subject, inbound_snippet, body, status, auto_send_eligible, "
                " findings_json, sources_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
                (
                    interaction_id,
                    intent,
                    party,
                    from_unit,
                    unit,
                    case_ref,
                    priority,
                    inbound_subject,
                    inbound_snippet,
                    body,
                    int(auto_send_eligible),
                    json.dumps([f.model_dump() for f in findings]),
                    json.dumps([s.model_dump() for s in sources]),
                    _now_iso(),
                ),
            )
            return int(cur.lastrowid or 0)

    def get_draft(self, draft_id: int) -> Draft | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = cur.fetchone()
        return _to_draft(row) if row else None

    def list_drafts(self, status: str | None = None) -> list[Draft]:
        with self._cursor() as cur:
            if status:
                cur.execute("SELECT * FROM drafts WHERE status = ? ORDER BY id DESC", (status,))
            else:
                cur.execute("SELECT * FROM drafts ORDER BY id DESC")
            rows = cur.fetchall()
        return [_to_draft(r) for r in rows]

    def update_draft_body(
        self, draft_id: int, *, body: str, findings: list[GuardrailFinding]
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE drafts SET body = ?, findings_json = ? WHERE id = ?",
                (body, json.dumps([f.model_dump() for f in findings]), draft_id),
            )

    def set_draft_status(self, draft_id: int, status: str) -> None:
        with self._cursor() as cur:
            cur.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))

    # ── Tickets ──────────────────────────────────────────────────────────────
    def add_ticket(
        self,
        *,
        title: str,
        type: str,
        priority: str,
        unit: str,
        case_ref: str,
        assignee: str,
        due_date: str = "",
        description: str = "",
        source: str = "email",
        source_interaction_id: int | None = None,
        source_resolution_id: int | None = None,
        topic_key: str = "",
    ) -> Ticket:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO tickets "
                "(title, type, status, priority, unit, case_ref, assignee, due_date, "
                " description, source, source_interaction_id, source_resolution_id, "
                " topic_key, created_at) "
                "VALUES (?, ?, 'todo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    title,
                    type,
                    priority,
                    unit,
                    case_ref,
                    assignee,
                    due_date,
                    description,
                    source,
                    source_interaction_id,
                    source_resolution_id,
                    topic_key,
                    _now_iso(),
                ),
            )
            ticket_id = int(cur.lastrowid or 0)
            cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = cur.fetchone()
        return _to_ticket(row)

    def get_ticket(self, ticket_id: int) -> Ticket | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = cur.fetchone()
        return _to_ticket(row) if row else None

    def list_tickets(self) -> list[Ticket]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tickets ORDER BY id DESC")
            rows = cur.fetchall()
        return [_to_ticket(r) for r in rows]

    def set_ticket_status(self, ticket_id: int, status: str) -> Ticket | None:
        with self._cursor() as cur:
            cur.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
            cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = cur.fetchone()
        return _to_ticket(row) if row else None

    # ── Resolutions ──────────────────────────────────────────────────────────
    def add_resolution(
        self,
        *,
        title: str,
        effective_date: str,
        signed: bool,
        summary: str,
        keywords: str,
        unit: str = "",
    ) -> Resolution:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO resolutions "
                "(title, effective_date, signed, summary, keywords, unit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, effective_date, int(signed), summary, keywords, unit),
            )
            res_id = int(cur.lastrowid or 0)
        return Resolution(
            id=res_id,
            title=title,
            effective_date=effective_date,
            signed=signed,
            summary=summary,
            keywords=keywords,
            unit=unit,
        )

    def list_resolutions(self) -> list[Resolution]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM resolutions ORDER BY id DESC")
            rows = cur.fetchall()
        return [_to_resolution(r) for r in rows]

    def list_signed_resolutions(self) -> list[Resolution]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM resolutions WHERE signed = 1")
            rows = cur.fetchall()
        return [_to_resolution(r) for r in rows]


# ── Row → schema mappers ─────────────────────────────────────────────────────
def _to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=int(row["id"]),
        title=str(row["title"]),
        category=str(row["category"]),
        effective_date=str(row["effective_date"]),
        created_at=str(row["created_at"]),
    )


def _to_draft(row: sqlite3.Row) -> Draft:
    findings = [GuardrailFinding(**f) for f in json.loads(row["findings_json"])]
    sources = [Source(**s) for s in json.loads(row["sources_json"])]
    return Draft(
        id=int(row["id"]),
        interaction_id=int(row["interaction_id"]),
        intent=str(row["intent"]),
        party=str(row["party"]),
        from_unit=str(row["from_unit"]),
        unit=str(row["unit"]),
        case_ref=str(row["case_ref"]),
        priority=str(row["priority"]),
        inbound_subject=str(row["inbound_subject"]),
        inbound_snippet=str(row["inbound_snippet"]),
        body=str(row["body"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        auto_send_eligible=bool(row["auto_send_eligible"]),
        findings=findings,
        sources=sources,
        created_at=str(row["created_at"]),
    )


def _to_ticket(row: sqlite3.Row) -> Ticket:
    sii = row["source_interaction_id"]
    sri = row["source_resolution_id"]
    return Ticket(
        id=int(row["id"]),
        title=str(row["title"]),
        type=str(row["type"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        priority=str(row["priority"]),
        unit=str(row["unit"]),
        case_ref=str(row["case_ref"]),
        assignee=str(row["assignee"]),
        source_interaction_id=int(sii) if sii is not None else None,
        created_at=str(row["created_at"]),
        due_date=str(row["due_date"]),
        description=str(row["description"]),
        source=str(row["source"]),  # type: ignore[arg-type]
        source_resolution_id=int(sri) if sri is not None else None,
        topic_key=str(row["topic_key"]),
    )


def _to_resolution(row: sqlite3.Row) -> Resolution:
    return Resolution(
        id=int(row["id"]),
        title=str(row["title"]),
        effective_date=str(row["effective_date"]),
        signed=bool(row["signed"]),
        summary=str(row["summary"]),
        keywords=str(row["keywords"]),
        unit=str(row["unit"]),
    )
