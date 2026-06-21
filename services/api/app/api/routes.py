"""REST routes — mirrors the prototype API, wired onto the ports.

The path table maps 1:1 to the eventual API Gateway routes (SOLUTION_DESIGN §5).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.api.deps import LLMDep, RepoDep, SettingsDep, get_current_user
from app.domain import drafting, intake, rag
from app.domain import seed as seed_module
from app.schemas import (
    AnalyzeIn,
    AnalyzeOut,
    AskIn,
    AskOut,
    AssistConfig,
    Document,
    DocumentIn,
    Draft,
    DraftEdit,
    EmailIn,
    Health,
    InboxOut,
    Resolution,
    Source,
    Ticket,
    TicketIn,
    TicketStatusIn,
)

router = APIRouter(prefix="/api")

# Health is unauthenticated (deploy smoke test + load-balancer probes hit it
# with no token). Everything else requires an authenticated principal when
# ``auth_enabled`` is on; the dependency is a no-op (synthetic dev user) when off.
public_router = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


def _runtime(request: Request) -> dict[str, bool]:
    runtime: dict[str, bool] = request.app.state.runtime
    return runtime


# ── Health ───────────────────────────────────────────────────────────────────
@public_router.get("/health", response_model=Health)
def health(request: Request, settings: SettingsDep) -> Health:
    rt = _runtime(request)
    available = rt["assist_enabled"] and not rt["kill_switch"]
    from app import __version__

    return Health(
        status="ok",
        engine=settings.resolve_provider(),
        repo_backend=settings.repo_backend,
        assist_available=available,
        version=__version__,
    )


# ── Seed ─────────────────────────────────────────────────────────────────────
@router.post("/seed")
def seed(repo: RepoDep, llm: LLMDep) -> dict[str, int]:
    return seed_module.seed(repo, llm)


# ── Documents ────────────────────────────────────────────────────────────────
@router.get("/documents", response_model=list[Document])
def list_documents(repo: RepoDep) -> list[Document]:
    return repo.list_documents()


@router.post("/documents", response_model=Document)
def add_document(payload: DocumentIn, repo: RepoDep) -> Document:
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="Title and content are required.")
    existing = repo.get_document_by_title(title)
    if existing is not None:
        if not payload.overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"A document titled '{title}' already exists.",
            )
        repo.delete_document_by_title(title)
    effective = payload.effective_date.strip() or date.today().isoformat()
    chunks = rag.chunk_document(title, content)
    return repo.add_document(
        title=title,
        content=content,
        category=payload.category or "general",
        effective_date=effective,
        chunks=chunks,
    )


@router.post("/documents/analyze", response_model=AnalyzeOut)
def analyze_document(payload: AnalyzeIn, repo: RepoDep, llm: LLMDep) -> AnalyzeOut:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="No content to analyze.")
    meta = llm.suggest_metadata(content=content, filename=payload.filename)
    chunks = rag.chunk_document(meta["title"], content)
    return AnalyzeOut(
        title=meta["title"],
        category=meta["category"],
        effective_date=date.today().isoformat(),
        char_count=len(content),
        chunk_count=len(chunks),
        preview=content[:280],
        llm=llm.__class__.__name__,
    )


# ── Ask (document brain) ─────────────────────────────────────────────────────
@router.post("/ask", response_model=AskOut)
def ask(payload: AskIn, repo: RepoDep, llm: LLMDep) -> AskOut:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask a question first.")
    hits = rag.search(question, repo.corpus(), limit=5)
    context = [h.snippet for h in hits]
    answer = llm.answer_question(question=question, context=context)
    sources = [Source(title=h.title, snippet=h.snippet[:240], kind=h.kind) for h in hits]
    return AskOut(answer=answer, sources=sources)


# ── Inbox (inbound email → draft or task) ────────────────────────────────────
@router.post("/inbox", response_model=InboxOut)
def inbox(payload: EmailIn, repo: RepoDep, llm: LLMDep, settings: SettingsDep) -> InboxOut:
    if intake.is_task_email(payload.sender, payload.subject, settings.chairman_emails):
        ticket = drafting.create_task_from_email(repo, payload)
        return InboxOut(kind="task", ticket=ticket)
    draft = drafting.process_inbound(repo, llm, payload)
    return InboxOut(kind="draft", draft=draft)


# ── Drafts ───────────────────────────────────────────────────────────────────
@router.get("/drafts", response_model=list[Draft])
def list_drafts(repo: RepoDep, status: str | None = None) -> list[Draft]:
    return repo.list_drafts(status)


@router.get("/drafts/{draft_id}", response_model=Draft)
def get_draft(draft_id: int, repo: RepoDep) -> Draft:
    draft = repo.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


@router.put("/drafts/{draft_id}", response_model=Draft)
def edit_draft(draft_id: int, payload: DraftEdit, repo: RepoDep) -> Draft:
    draft = drafting.edit_draft(repo, draft_id, payload.body)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=Draft)
def approve_draft(
    draft_id: int,
    repo: RepoDep,
    payload: Annotated[DraftEdit | None, Body()] = None,
) -> Draft:
    body = payload.body if payload is not None else None
    try:
        return drafting.approve_draft(repo, draft_id, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Draft not found.") from exc
    except drafting.GuardrailBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/discard", response_model=Draft)
def discard_draft(draft_id: int, repo: RepoDep) -> Draft:
    draft = drafting.discard_draft(repo, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


# ── Tickets (trustee board) ──────────────────────────────────────────────────
@router.get("/tickets", response_model=list[Ticket])
def list_tickets(repo: RepoDep) -> list[Ticket]:
    return repo.list_tickets()


@router.post("/tickets", response_model=Ticket)
def create_ticket(payload: TicketIn, repo: RepoDep) -> Ticket:
    try:
        return drafting.create_task(
            repo,
            title=payload.title,
            type=payload.type,
            priority=payload.priority,
            unit=payload.unit,
            due_date=payload.due_date,
            description=payload.description,
            source=payload.source,
            source_resolution_id=payload.source_resolution_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tickets/{ticket_id}/status", response_model=Ticket)
def set_ticket_status(ticket_id: int, payload: TicketStatusIn, repo: RepoDep) -> Ticket:
    ticket = repo.set_ticket_status(ticket_id, payload.status)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


# ── Resolutions register ─────────────────────────────────────────────────────
@router.get("/resolutions", response_model=list[Resolution])
def list_resolutions(repo: RepoDep) -> list[Resolution]:
    return repo.list_resolutions()


# ── Assist config (global toggle + kill-switch) ──────────────────────────────
@router.get("/assist/config", response_model=AssistConfig)
def get_assist_config(request: Request) -> AssistConfig:
    rt = _runtime(request)
    return AssistConfig(
        assist_enabled=rt["assist_enabled"],
        kill_switch=rt["kill_switch"],
        available=rt["assist_enabled"] and not rt["kill_switch"],
    )


@router.post("/assist/config", response_model=AssistConfig)
def set_assist_config(payload: AssistConfig, request: Request) -> AssistConfig:
    rt = _runtime(request)
    rt["assist_enabled"] = payload.assist_enabled
    rt["kill_switch"] = payload.kill_switch
    return AssistConfig(
        assist_enabled=rt["assist_enabled"],
        kill_switch=rt["kill_switch"],
        available=rt["assist_enabled"] and not rt["kill_switch"],
    )
