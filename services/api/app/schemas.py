"""Pydantic request/response models.

Field names match the prototype's dataclasses (``prototype/app/models.py``) so
the existing dashboard front-end keeps working unchanged. These are the wire
contract for the REST API; persistence rows are mapped to/from these in the
adapters.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["block", "warn", "info"]
SourceKind = Literal["document", "interaction"]
DraftStatus = Literal["pending", "filed", "auto_filed", "discarded"]
TicketStatus = Literal["todo", "in_progress", "done"]
TicketSource = Literal["email", "chair_email", "manual", "resolution"]


# ── Documents ────────────────────────────────────────────────────────────────
class DocumentIn(BaseModel):
    title: str
    content: str
    category: str = "general"
    effective_date: str = ""
    overwrite: bool = False


class Document(BaseModel):
    id: int
    title: str
    category: str
    effective_date: str
    created_at: str


class AnalyzeIn(BaseModel):
    content: str
    filename: str = ""


class AnalyzeOut(BaseModel):
    title: str
    category: str
    effective_date: str
    char_count: int
    chunk_count: int
    preview: str
    llm: str


# ── Ask (document brain Q&A) ─────────────────────────────────────────────────
class AskIn(BaseModel):
    question: str


class Source(BaseModel):
    title: str
    snippet: str
    kind: SourceKind


class AskOut(BaseModel):
    answer: str
    sources: list[Source]


# ── Inbound email → draft / task ─────────────────────────────────────────────
class EmailIn(BaseModel):
    sender: str
    subject: str
    body: str
    from_unit: str = ""


class InboxOut(BaseModel):
    """An inbound email becomes either a draft reply or a board task."""

    kind: Literal["draft", "task"]
    draft: Draft | None = None
    ticket: Ticket | None = None


class GuardrailFinding(BaseModel):
    rule: str
    severity: Severity
    message: str


class Draft(BaseModel):
    id: int
    interaction_id: int
    intent: str
    party: str
    from_unit: str
    unit: str
    case_ref: str
    priority: str
    inbound_subject: str
    inbound_snippet: str
    body: str
    status: DraftStatus
    auto_send_eligible: bool
    findings: list[GuardrailFinding] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    created_at: str = ""


class DraftEdit(BaseModel):
    body: str


# ── Tickets (trustee board) ──────────────────────────────────────────────────
class Ticket(BaseModel):
    id: int
    title: str
    type: str
    status: TicketStatus
    priority: str
    unit: str
    case_ref: str
    assignee: str
    source_interaction_id: int | None = None
    created_at: str = ""
    due_date: str = ""
    description: str = ""
    source: TicketSource = "email"
    source_resolution_id: int | None = None
    topic_key: str = ""


class TicketIn(BaseModel):
    title: str
    type: str = "general"
    priority: str = "normal"
    unit: str = ""
    due_date: str = ""
    description: str = ""
    source: TicketSource = "manual"
    source_resolution_id: int | None = None


class TicketStatusIn(BaseModel):
    status: TicketStatus


# ── Resolutions register ─────────────────────────────────────────────────────
class Resolution(BaseModel):
    id: int
    title: str
    effective_date: str
    signed: bool
    summary: str
    keywords: str
    unit: str = ""


# ── Misc ─────────────────────────────────────────────────────────────────────
class Health(BaseModel):
    status: Literal["ok"]
    engine: str
    repo_backend: str
    assist_available: bool
    version: str


class AssistConfig(BaseModel):
    assist_enabled: bool
    kill_switch: bool
    available: bool


# Resolve forward references now that Draft and Ticket are defined.
InboxOut.model_rebuild()
