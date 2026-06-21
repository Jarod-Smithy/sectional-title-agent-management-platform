"""Draft Composer (agent #3) + correspondence flow.

Ties together intake → RAG → LLM draft → Governance Guardian, persisting an
inbound interaction and a pending draft. On approval it FILES an outbound
interaction (it does not email) and creates a trustee ticket (Records Clerk +
Ticketing Agent). Bare acknowledgements are auto-filed (no ticket) — the one
configured exception to human-in-the-loop.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from . import db, guardrails, intake, rag, threads
from .llm import get_llm
from .models import Draft, EmailIn, GuardrailFinding, Source, Ticket

# Intents whose bare acknowledgement may be auto-filed if fully clean.
_AUTO_SEND_INTENTS = {"acknowledgement"}


def _row_to_draft(row: db.sqlite3.Row) -> Draft:
    findings = [GuardrailFinding(**f) for f in json.loads(row["findings_json"])]
    sources = [Source(**s) for s in json.loads(row["sources_json"])]
    return Draft(
        id=row["id"],
        interaction_id=row["interaction_id"],
        intent=row["intent"],
        party=row["party"],
        from_unit=row["from_unit"],
        unit=row["unit"],
        case_ref=row["case_ref"],
        priority=row["priority"],
        inbound_subject=row["inbound_subject"],
        inbound_snippet=row["inbound_snippet"],
        body=row["body"],
        status=row["status"],
        auto_send_eligible=bool(row["auto_send_eligible"]),
        findings=findings,
        sources=sources,
        created_at=row["created_at"],
    )


def process_inbound(email: EmailIn) -> Draft:
    party = intake.extract_party(email.sender)
    intent = intake.classify_intent(email.subject, email.body)
    # The matter's "about" unit comes from the subject/body; the sender's own
    # unit is separate. Filing against the wrong unit (e.g. a noise complaint
    # against the complainant) is a real ledger-integrity bug, so keep them apart.
    about_unit = intake.extract_unit(email.subject, email.body) or email.from_unit
    from_unit = email.from_unit
    prio = intake.priority(email.subject, email.body)
    ref = intake.case_ref(intent, about_unit)
    snippet = email.body.strip().replace("\n", " ")[:200]

    # Consolidate this mail with any earlier thread about the same matter.
    topic_key = threads.assign_topic_key(email.subject, email.body, party, about_unit)

    # 1. Log the inbound interaction (filed against the unit it is ABOUT).
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO interactions "
            "(direction, party, subject, body, unit, case_ref, topic_key, created_at) "
            "VALUES ('inbound', ?, ?, ?, ?, ?, ?, ?)",
            (party, email.subject, email.body, about_unit, ref, topic_key, db.now_iso()),
        )
        interaction_id = cur.lastrowid

    # 2. Retrieve grounding context.
    hits = rag.search(f"{email.subject} {email.body}", limit=5)
    context = [h.snippet for h in hits]
    sources = [Source(title=h.title, snippet=h.snippet[:240], kind=h.kind) for h in hits]

    # 3. Compose draft.
    body = get_llm().draft_reply(
        subject=email.subject, body=email.body, party=party, context=context
    )

    # 4. Governance Guardian screen (matter-scoped to the about-unit).
    findings = guardrails.screen(body, about_unit)
    auto_send = intent in _AUTO_SEND_INTENTS and not guardrails.has_block(findings)

    with db.cursor() as cur:
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
                about_unit,
                ref,
                prio,
                email.subject,
                snippet,
                body,
                int(auto_send),
                json.dumps([asdict(f) for f in findings]),
                json.dumps([asdict(s) for s in sources]),
                db.now_iso(),
            ),
        )
        draft_id = cur.lastrowid

    # 5. Auto-file a clean bare acknowledgement (the one configured exception).
    if auto_send:
        _file_reply(draft_id, create_ticket=False, status="auto_filed")

    result = get_draft(draft_id)
    assert result is not None
    return result


def list_drafts(status: str | None = None) -> list[Draft]:
    with db.cursor() as cur:
        if status:
            cur.execute("SELECT * FROM drafts WHERE status = ? ORDER BY id DESC", (status,))
        else:
            cur.execute("SELECT * FROM drafts ORDER BY id DESC")
        rows = cur.fetchall()
    return [_row_to_draft(r) for r in rows]


def get_draft(draft_id: int) -> Draft | None:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        row = cur.fetchone()
    return _row_to_draft(row) if row else None


def edit_draft(draft_id: int, body: str) -> Draft | None:
    existing = get_draft(draft_id)
    if existing is None:
        return None
    findings = guardrails.screen(body, existing.unit)
    with db.cursor() as cur:
        cur.execute(
            "UPDATE drafts SET body = ?, findings_json = ? WHERE id = ?",
            (body, json.dumps([asdict(f) for f in findings]), draft_id),
        )
    return get_draft(draft_id)


def discard_draft(draft_id: int) -> Draft | None:
    with db.cursor() as cur:
        cur.execute(
            "UPDATE drafts SET status = 'discarded' WHERE id = ? AND status = 'pending'",
            (draft_id,),
        )
    return get_draft(draft_id)


class GuardrailBlocked(Exception):
    """Raised when an approve is attempted on a draft with BLOCK findings."""


def _file_reply(draft_id: int, *, create_ticket: bool, status: str) -> None:
    """File the outbound interaction (Records Clerk) and optionally raise a
    ticket (Ticketing Agent). This FILES a record — it does not send an email."""
    draft = get_draft(draft_id)
    assert draft is not None
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO interactions "
            "(direction, party, subject, body, unit, case_ref, created_at) "
            "VALUES ('outbound', ?, ?, ?, ?, ?, ?)",
            (
                draft.party,
                f"RE: {draft.inbound_subject or draft.case_ref}",
                draft.body,
                draft.unit,
                draft.case_ref,
                db.now_iso(),
            ),
        )
        if create_ticket:
            cur.execute(
                "INSERT INTO tickets "
                "(title, type, status, priority, unit, case_ref, assignee, "
                " source_interaction_id, created_at) "
                "VALUES (?, ?, 'todo', ?, ?, ?, ?, ?, ?)",
                (
                    f"{draft.intent.title()} — {draft.party}"
                    + (f" ({draft.unit})" if draft.unit else ""),
                    draft.intent,
                    draft.priority,
                    draft.unit,
                    draft.case_ref,
                    "Chairperson",
                    draft.interaction_id,
                    db.now_iso(),
                ),
            )
        cur.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))


def approve_draft(draft_id: int, body: str | None = None) -> Draft:
    """Approve = file the (possibly edited) reply + raise a ticket. Re-screens
    the exact text being approved server-side, so an in-place edit can never
    bypass the Governance Guardian."""
    draft = get_draft(draft_id)
    if draft is None:
        raise KeyError(draft_id)
    if body is not None and body != draft.body:
        draft = edit_draft(draft_id, body)
        assert draft is not None
    if guardrails.has_block(draft.findings):
        raise GuardrailBlocked(
            "This reply proposes an action that needs a signed resolution (or hits "
            "an absolute no-go). Edit the wording before filing."
        )
    _file_reply(draft_id, create_ticket=True, status="filed")
    result = get_draft(draft_id)
    assert result is not None
    return result


def _row_to_ticket(row: db.sqlite3.Row) -> Ticket:
    return Ticket(**dict(row))


def create_task_from_email(email: EmailIn) -> Ticket:
    """Chairman task instruction → a board task (no reply, no screening).

    The inbound email is still filed as an interaction (a record of what was
    asked), then a ticket is raised directly. The task is just a reminder; the
    Governance Guardian screens later, when the action is actually taken.
    """
    party = intake.extract_party(email.sender)
    intent = intake.classify_intent(email.subject, email.body)
    about_unit = intake.extract_unit(email.subject, email.body) or email.from_unit
    prio = intake.priority(email.subject, email.body)
    title = intake.task_title_from_subject(email.subject)
    due = intake.extract_due_date(f"{email.subject}\n{email.body}")
    ref = intake.case_ref(intent, about_unit)
    topic_key = threads.assign_topic_key(email.subject, email.body, party, about_unit)

    with db.cursor() as cur:
        # File the instruction as an inbound record.
        cur.execute(
            "INSERT INTO interactions "
            "(direction, party, subject, body, unit, case_ref, topic_key, created_at) "
            "VALUES ('inbound', ?, ?, ?, ?, ?, ?, ?)",
            (party, email.subject, email.body, about_unit, ref, topic_key, db.now_iso()),
        )
        interaction_id = cur.lastrowid

        # Raise the task, assigned (as always) to the accountable human.
        cur.execute(
            "INSERT INTO tickets "
            "(title, type, status, priority, unit, case_ref, assignee, due_date, "
            " description, source, source_interaction_id, topic_key, created_at) "
            "VALUES (?, ?, 'todo', ?, ?, ?, 'Chairperson', ?, ?, 'chair_email', ?, ?, ?)",
            (
                title,
                intent,
                prio,
                about_unit,
                ref,
                due,
                email.body.strip(),
                interaction_id,
                topic_key,
                db.now_iso(),
            ),
        )
        ticket_id = cur.lastrowid
        cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
    return _row_to_ticket(row)


def create_task(
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
    """Raise a standalone board task (manual entry or from a resolution).

    Always assigned to the accountable human; no guardrail screening (a task is
    just a reminder)."""
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("A task needs a title.")
    ref = intake.case_ref(type, unit)
    # Link the task to any existing matter so the board can surface related mail.
    topic_key = threads.topic_key_for_text(clean_title, description, "", unit)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tickets "
            "(title, type, status, priority, unit, case_ref, assignee, due_date, "
            " description, source, source_resolution_id, topic_key, created_at) "
            "VALUES (?, ?, 'todo', ?, ?, ?, 'Chairperson', ?, ?, ?, ?, ?, ?)",
            (
                clean_title,
                type or "general",
                priority or "normal",
                unit or "",
                ref,
                due_date or "",
                (description or "").strip(),
                source or "manual",
                source_resolution_id,
                topic_key,
                db.now_iso(),
            ),
        )
        ticket_id = cur.lastrowid
        cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
    return _row_to_ticket(row)
