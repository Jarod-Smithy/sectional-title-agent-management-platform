"""Draft Composer + correspondence flow — orchestration over the ports.

Ties together intake → RAG → LLM draft → Governance Guardian, persisting an
inbound interaction and a pending draft. On approval it FILES an outbound
interaction (it does not email) and raises a trustee ticket. Bare
acknowledgements are auto-filed (no ticket) — the one configured exception to
human-in-the-loop.

Every function takes the ``Repository`` and ``LLM`` ports explicitly, so this
module has no global state and is wired by the API layer.
"""

from __future__ import annotations

from app.domain import guardrails, intake, rag, threads
from app.ports.llm import LLM
from app.ports.repository import Repository
from app.schemas import Draft, EmailIn, Source, Ticket

_AUTO_SEND_INTENTS = {"acknowledgement"}


class GuardrailBlocked(Exception):
    """Raised when an approve is attempted on a draft with BLOCK findings."""


def process_inbound(repo: Repository, llm: LLM, email: EmailIn) -> Draft:
    party = intake.extract_party(email.sender)
    intent = intake.classify_intent(email.subject, email.body)
    # The matter's "about" unit comes from the subject/body; the sender's own
    # unit is separate (filing against the wrong unit is a ledger-integrity bug).
    about_unit = intake.extract_unit(email.subject, email.body) or email.from_unit
    prio = intake.priority(email.subject, email.body)
    ref = intake.case_ref(intent, about_unit)
    snippet = email.body.strip().replace("\n", " ")[:200]
    topic_key = threads.topic_key_for_text(email.subject, email.body, party, about_unit)

    # 1. Log the inbound interaction (filed against the unit it is ABOUT).
    interaction_id = repo.add_interaction(
        direction="inbound",
        party=party,
        subject=email.subject,
        body=email.body,
        unit=about_unit,
        case_ref=ref,
        topic_key=topic_key,
    )

    # 2. Retrieve grounding context.
    hits = rag.search(f"{email.subject} {email.body}", repo.corpus(), limit=5)
    context = [h.snippet for h in hits]
    sources = [Source(title=h.title, snippet=h.snippet[:240], kind=h.kind) for h in hits]

    # 3. Compose draft.
    body = llm.draft_reply(subject=email.subject, body=email.body, party=party, context=context)

    # 4. Governance Guardian screen (matter-scoped to the about-unit).
    findings = guardrails.screen(body, about_unit, repo.list_signed_resolutions())
    auto_send = intent in _AUTO_SEND_INTENTS and not guardrails.has_block(findings)

    draft_id = repo.add_draft(
        interaction_id=interaction_id,
        intent=intent,
        party=party,
        from_unit=email.from_unit,
        unit=about_unit,
        case_ref=ref,
        priority=prio,
        inbound_subject=email.subject,
        inbound_snippet=snippet,
        body=body,
        auto_send_eligible=auto_send,
        findings=findings,
        sources=sources,
    )

    # 5. Auto-file a clean bare acknowledgement (the one configured exception).
    if auto_send:
        _file_reply(repo, draft_id, create_ticket=False, status="auto_filed")

    result = repo.get_draft(draft_id)
    if result is None:
        raise RuntimeError(f"draft {draft_id} missing immediately after write")
    return result


def edit_draft(repo: Repository, draft_id: int, body: str) -> Draft | None:
    existing = repo.get_draft(draft_id)
    if existing is None:
        return None
    findings = guardrails.screen(body, existing.unit, repo.list_signed_resolutions())
    repo.update_draft_body(draft_id, body=body, findings=findings)
    return repo.get_draft(draft_id)


def discard_draft(repo: Repository, draft_id: int) -> Draft | None:
    existing = repo.get_draft(draft_id)
    if existing is None:
        return None
    if existing.status == "pending":
        repo.set_draft_status(draft_id, "discarded")
    return repo.get_draft(draft_id)


def approve_draft(repo: Repository, draft_id: int, body: str | None = None) -> Draft:
    """Approve = file the (possibly edited) reply + raise a ticket. Re-screens
    the exact text being approved server-side, so an in-place edit can never
    bypass the Governance Guardian."""
    draft = repo.get_draft(draft_id)
    if draft is None:
        raise KeyError(draft_id)
    if body is not None and body != draft.body:
        edited = edit_draft(repo, draft_id, body)
        if edited is None:
            raise KeyError(draft_id)
        draft = edited
    if guardrails.has_block(draft.findings):
        raise GuardrailBlocked(
            "This reply proposes an action that needs a signed resolution (or hits "
            "an absolute no-go). Edit the wording before filing."
        )
    _file_reply(repo, draft_id, create_ticket=True, status="filed")
    result = repo.get_draft(draft_id)
    if result is None:
        raise RuntimeError(f"draft {draft_id} missing immediately after filing")
    return result


def _file_reply(repo: Repository, draft_id: int, *, create_ticket: bool, status: str) -> None:
    """File the outbound interaction and optionally raise a ticket. This FILES a
    record — it does not send an email."""
    draft = repo.get_draft(draft_id)
    if draft is None:
        raise KeyError(draft_id)
    repo.add_interaction(
        direction="outbound",
        party=draft.party,
        subject=f"RE: {draft.inbound_subject or draft.case_ref}",
        body=draft.body,
        unit=draft.unit,
        case_ref=draft.case_ref,
    )
    if create_ticket:
        title = f"{draft.intent.title()} — {draft.party}" + (
            f" ({draft.unit})" if draft.unit else ""
        )
        repo.add_ticket(
            title=title,
            type=draft.intent,
            priority=draft.priority,
            unit=draft.unit,
            case_ref=draft.case_ref,
            assignee="Chairperson",
            source_interaction_id=draft.interaction_id,
        )
    repo.set_draft_status(draft_id, status)


def create_task_from_email(repo: Repository, email: EmailIn) -> Ticket:
    """Chairman task instruction → a board task (no reply, no screening)."""
    party = intake.extract_party(email.sender)
    intent = intake.classify_intent(email.subject, email.body)
    about_unit = intake.extract_unit(email.subject, email.body) or email.from_unit
    prio = intake.priority(email.subject, email.body)
    title = intake.task_title_from_subject(email.subject)
    due = intake.extract_due_date(f"{email.subject}\n{email.body}")
    ref = intake.case_ref(intent, about_unit)
    topic_key = threads.topic_key_for_text(email.subject, email.body, party, about_unit)

    interaction_id = repo.add_interaction(
        direction="inbound",
        party=party,
        subject=email.subject,
        body=email.body,
        unit=about_unit,
        case_ref=ref,
        topic_key=topic_key,
    )
    return repo.add_ticket(
        title=title,
        type=intent,
        priority=prio,
        unit=about_unit,
        case_ref=ref,
        assignee="Chairperson",
        due_date=due,
        description=email.body.strip(),
        source="chair_email",
        source_interaction_id=interaction_id,
        topic_key=topic_key,
    )


def create_task(
    repo: Repository,
    *,
    title: str,
    type: str = "general",
    priority: str = "normal",
    unit: str = "",
    due_date: str = "",
    description: str = "",
    source: str = "manual",
    source_resolution_id: int | None = None,
) -> Ticket:
    """Raise a standalone board task (manual entry or from a resolution)."""
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("A task needs a title.")
    ref = intake.case_ref(type, unit)
    topic_key = threads.topic_key_for_text(clean_title, description, "", unit)
    return repo.add_ticket(
        title=clean_title,
        type=type or "general",
        priority=priority or "normal",
        unit=unit or "",
        case_ref=ref,
        assignee="Chairperson",
        due_date=due_date or "",
        description=(description or "").strip(),
        source=source or "manual",
        source_resolution_id=source_resolution_id,
        topic_key=topic_key,
    )
