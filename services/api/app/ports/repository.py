"""Repository port — the single seam to persistence.

The domain calls these methods; SQLite (local) and DynamoDB (prod) implement
them. Methods are intentionally domain-level (``add_draft``, ``set_ticket_status``)
rather than raw SQL, so the same calls work over either backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas import (
    Document,
    Draft,
    GuardrailFinding,
    Resolution,
    Source,
    SourceKind,
    Ticket,
)


@dataclass(frozen=True)
class Chunk:
    """A structure-aware slice of a document, produced by the RAG chunker."""

    ordinal: int
    heading: str
    text: str  # clean content shown as a snippet
    context: str  # "Title › Heading" + overlap tail, used only for indexing
    char_start: int
    char_end: int


@dataclass(frozen=True)
class CorpusItem:
    """One retrievable unit for BM25 ranking (a doc chunk or an interaction)."""

    title: str
    snippet: str  # clean text shown to the user
    index_text: str  # text fed to the ranker (context + content)
    kind: SourceKind  # "document" | "interaction"


class Repository(Protocol):
    """Persistence operations the domain needs. Implemented per backend."""

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def init(self) -> None: ...

    def reset(self) -> None: ...

    # ── Documents + retrieval corpus ─────────────────────────────────────────
    def add_document(
        self,
        *,
        title: str,
        content: str,
        category: str,
        effective_date: str,
        chunks: list[Chunk],
    ) -> Document: ...

    def get_document_by_title(self, title: str) -> Document | None: ...

    def delete_document_by_title(self, title: str) -> bool: ...

    def list_documents(self) -> list[Document]: ...

    def count_documents(self) -> int: ...

    def corpus(self, *, interaction_limit: int = 200) -> list[CorpusItem]: ...

    # ── Interactions (correspondence ledger) ─────────────────────────────────
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
    ) -> int: ...

    # ── Drafts (draft-and-approve queue) ─────────────────────────────────────
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
    ) -> int: ...

    def get_draft(self, draft_id: int) -> Draft | None: ...

    def list_drafts(self, status: str | None = None) -> list[Draft]: ...

    def update_draft_body(
        self, draft_id: int, *, body: str, findings: list[GuardrailFinding]
    ) -> None: ...

    def set_draft_status(self, draft_id: int, status: str) -> None: ...

    # ── Tickets (trustee board) ──────────────────────────────────────────────
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
    ) -> Ticket: ...

    def get_ticket(self, ticket_id: int) -> Ticket | None: ...

    def list_tickets(self) -> list[Ticket]: ...

    def set_ticket_status(self, ticket_id: int, status: str) -> Ticket | None: ...

    # ── Resolutions register ─────────────────────────────────────────────────
    def add_resolution(
        self,
        *,
        title: str,
        effective_date: str,
        signed: bool,
        summary: str,
        keywords: str,
        unit: str = "",
    ) -> Resolution: ...

    def list_resolutions(self) -> list[Resolution]: ...

    def list_signed_resolutions(self) -> list[Resolution]: ...
