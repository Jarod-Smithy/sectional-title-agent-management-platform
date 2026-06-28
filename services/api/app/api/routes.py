"""REST routes — mirrors the prototype API, wired onto the ports.

The path table maps 1:1 to the eventual API Gateway routes (SOLUTION_DESIGN §5).
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.adapters.s3_documents import extract_text
from app.api.deps import CurrentUser, LLMDep, RepoDep, SettingsDep, get_current_user
from app.domain import approvals, drafting, intake, rag
from app.domain import sdlc as sdlc_domain
from app.domain import seed as seed_module
from app.ports.documents import DocumentStore
from app.ports.email import EmailError, EmailSender
from app.ports.sdlc import IssueTracker, IssueTrackerError
from app.schemas import (
    AnalyzeIn,
    AnalyzeOut,
    AskIn,
    AskOut,
    AssistConfig,
    BugReportIn,
    Document,
    DocumentIn,
    Draft,
    DraftEdit,
    EmailIn,
    FeatureRequestAck,
    FeatureRequestIn,
    Health,
    InboxOut,
    IssueCreatedOut,
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


def _email_sender(request: Request) -> EmailSender:
    sender: EmailSender = request.app.state.email
    return sender


def _document_store(request: Request) -> DocumentStore:
    """Return the configured S3 document store, or 503 when uploads are off."""
    store: DocumentStore | None = getattr(request.app.state, "documents", None)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Document upload is not configured (no storage bucket set).",
        )
    return store


def _issue_tracker(request: Request) -> IssueTracker:
    tracker: IssueTracker = request.app.state.issue_tracker
    return tracker


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
def seed(repo: RepoDep, llm: LLMDep, settings: SettingsDep) -> dict[str, int]:
    if not settings.seed_enabled:
        raise HTTPException(status_code=403, detail="Demo seeding is disabled.")
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


# ── Document upload (presigned S3 PUT → confirm → register + index) ──────────
# NOTE: the camelCase field names below are the EXACT wire contract the frontend
# depends on (filename/contentType in, documentId/key/uploadUrl out). pep8-naming
# (N) is not in the selected ruff rule-set, so they need no per-line ignores.
class UploadUrlIn(BaseModel):
    """Request a presigned URL to upload a file directly to S3."""

    filename: str
    contentType: str = "application/octet-stream"


class UploadUrlOut(BaseModel):
    """A presigned PUT the client uploads the raw file bytes to."""

    documentId: str
    key: str
    uploadUrl: str


def _safe_filename(filename: str) -> str:
    """Reduce a client-supplied name to a safe S3 object basename."""
    base = PurePosixPath(filename.replace("\\", "/")).name.strip()
    return base or "upload.bin"


@router.post("/documents/upload-url", response_model=UploadUrlOut)
def create_upload_url(
    payload: UploadUrlIn, request: Request, settings: SettingsDep
) -> UploadUrlOut:
    store = _document_store(request)
    filename = _safe_filename(payload.filename)
    document_id = uuid.uuid4().hex
    key = f"uploads/{document_id}/{filename}"
    upload_url = store.presign_put(
        key=key,
        content_type=payload.contentType or "application/octet-stream",
        expires_in=settings.upload_url_expiry_seconds,
    )
    return UploadUrlOut(documentId=document_id, key=key, uploadUrl=upload_url)


@router.post("/documents/{document_id}/confirm", response_model=Document)
def confirm_upload(document_id: str, request: Request, repo: RepoDep) -> Document:
    """Read the uploaded object back from S3, extract text, and register +
    index it exactly like the paste-text path."""
    store = _document_store(request)
    keys = store.list_keys(prefix=f"uploads/{document_id}/")
    if not keys:
        raise HTTPException(status_code=404, detail="No uploaded file found for this document.")
    key = keys[0]
    data = store.get_object(key=key)
    filename = PurePosixPath(key).name
    content = extract_text(filename, data)
    title = PurePosixPath(filename).stem or filename
    if repo.get_document_by_title(title) is not None:
        repo.delete_document_by_title(title)
    chunks = rag.chunk_document(title, content)
    return repo.add_document(
        title=title,
        content=content,
        category="general",
        effective_date=date.today().isoformat(),
        chunks=chunks,
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
def inbox(
    payload: EmailIn,
    repo: RepoDep,
    llm: LLMDep,
    settings: SettingsDep,
    request: Request,
) -> InboxOut:
    if intake.is_task_email(payload.sender, payload.subject, settings.chairman_emails):
        ticket = drafting.create_task_from_email(repo, payload)
        return InboxOut(kind="task", ticket=ticket)
    draft = drafting.process_inbound(repo, llm, payload, email_sender=_email_sender(request))
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
    request: Request,
    payload: Annotated[DraftEdit | None, Body()] = None,
) -> Draft:
    body = payload.body if payload is not None else None
    try:
        return drafting.approve_draft(repo, draft_id, body, email_sender=_email_sender(request))
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


# ── SDLC: capture a runtime error → labelled bug issue ───────────────────────
@router.post("/report-bug", response_model=IssueCreatedOut)
def report_bug(payload: BugReportIn, request: Request) -> IssueCreatedOut:
    """File a captured client-side error as an ``ai-sdlc``/``bug`` issue.

    With the SDLC pipeline disabled (default) the offline tracker records the
    report and returns ``created=false`` (HTTP 200) — the dashboard treats both
    paths as success so error capture never surfaces a second error.
    """
    title, body = sdlc_domain.format_bug_report(
        message=payload.message,
        stack=payload.stack,
        url=payload.url,
        user_agent=payload.user_agent,
        context=payload.context,
    )
    try:
        ref = _issue_tracker(request).create_issue(
            title=title, body=body, labels=("ai-sdlc", "bug")
        )
    except IssueTrackerError as exc:
        raise HTTPException(status_code=502, detail="Could not file the bug report.") from exc
    # ``created`` means "tracked", not necessarily "freshly opened": when the
    # GitHub adapter de-dupes a recurring error it returns the EXISTING open
    # issue's ``number``/``url`` (number > 0), so the dashboard still gets a
    # working tracking link. Only the offline log tracker yields number == 0.
    return IssueCreatedOut(number=ref.number, url=ref.url, created=ref.number > 0)


# ── SDLC: feature request → emailed approval magic-link → feature issue ───────
@router.post("/feature-request", response_model=FeatureRequestAck)
def feature_request(
    payload: FeatureRequestIn,
    user: CurrentUser,
    settings: SettingsDep,
    request: Request,
) -> FeatureRequestAck:
    """Email an HMAC-signed approval link to the configured approver.

    No issue is created here — opening the link (``/feature-request/approve``)
    is what files it. Returns 503 until the approver/secret/base URL are set.
    """
    if not (settings.approver_email and settings.approval_secret and settings.public_base_url):
        raise HTTPException(status_code=503, detail="Feature-request approval is not configured.")
    token = approvals.make_token(
        secret=settings.approval_secret,
        claims={
            "title": payload.title,
            "details": payload.details,
            "requester": user.username,
        },
        ttl_seconds=settings.feature_request_ttl_seconds,
    )
    link = f"{settings.public_base_url.rstrip('/')}/api/feature-request/approve?token={token}"
    subject, body = sdlc_domain.approval_email(
        title=payload.title, requester=user.username, link=link
    )
    try:
        _email_sender(request).send(to=settings.approver_email, subject=subject, body=body)
    except EmailError as exc:
        raise HTTPException(status_code=502, detail="Could not send the approval email.") from exc
    return FeatureRequestAck(status="pending_approval", approver=settings.approver_email)


@public_router.get("/feature-request/approve", response_class=HTMLResponse)
def approve_feature_request(token: str, settings: SettingsDep, request: Request) -> HTMLResponse:
    """Validate the magic-link token and file the feature as an issue.

    Public (the approver clicks it from email, with no session). The HMAC token
    is the authorisation; an invalid/expired token is a 400.
    """
    try:
        claims = approvals.read_token(secret=settings.approval_secret, token=token)
    except approvals.ApprovalError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired approval link.") from exc
    title, body = sdlc_domain.format_feature_request(
        title=str(claims.get("title", "")),
        details=str(claims.get("details", "")),
        requester=str(claims.get("requester", "")),
    )
    try:
        ref = _issue_tracker(request).create_issue(
            title=title, body=body, labels=("ai-sdlc", "feature")
        )
    except IssueTrackerError as exc:
        raise HTTPException(status_code=502, detail="Could not file the feature issue.") from exc
    link = (
        f'<p><a href="{ref.url}">View the tracked issue.</a></p>'
        if ref.number > 0
        else "<p>The request was logged.</p>"
    )
    return HTMLResponse(
        f"<!doctype html><html><body><h1>Feature request approved</h1>{link}</body></html>"
    )


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
