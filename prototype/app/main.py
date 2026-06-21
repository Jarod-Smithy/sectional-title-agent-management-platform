"""Stdlib HTTP server — REST API + static web UI for the prototype.

Zero third-party dependencies (no FastAPI/uvicorn) so it runs fully offline,
regardless of proxy/VPN state. The route table maps 1:1 to the eventual API
Gateway + Lambda design.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, db, drafting, intake, llm, rag, specialists, threads
from .models import (
    AskOut,
    Document,
    DocumentIn,
    EmailIn,
    Resolution,
    Source,
    Ticket,
    to_dict,
)

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ── Handlers (return plain JSON-able objects) ────────────────────────────────
def _health() -> dict:
    return {"status": "ok", "llm": llm.provider_name()}


def _reseed() -> dict:
    from .seed import seed

    return seed()


def _list_documents() -> list:
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, category, effective_date, created_at "
            "FROM documents ORDER BY id DESC"
        )
        return [to_dict(Document(**dict(r))) for r in cur.fetchall()]


def _add_document(payload: dict) -> dict:
    doc = DocumentIn(
        title=payload["title"],
        content=payload["content"],
        category=payload.get("category", "general"),
        effective_date=payload.get("effective_date") or db.now_iso()[:10],
    )
    if not doc.title.strip() or not doc.content.strip():
        raise ApiError(400, "A title and document content are required")
    overwrite = bool(payload.get("overwrite"))
    with db.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE title = ?", (doc.title,))
        existing = cur.fetchone()
        if existing and not overwrite:
            raise ApiError(
                409, f"A document titled “{doc.title}” already exists. Rename it or replace it."
            )
        if existing and overwrite:
            cur.execute("DELETE FROM documents WHERE id = ?", (existing["id"],))
        cur.execute(
            "INSERT INTO documents (title, category, effective_date, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (doc.title, doc.category, doc.effective_date, doc.content, db.now_iso()),
        )
        doc_id = cur.lastrowid
        rag.index_document(cur, doc_id, doc.title, doc.content)
        cur.execute(
            "SELECT id, title, category, effective_date, created_at " "FROM documents WHERE id = ?",
            (doc_id,),
        )
        return to_dict(Document(**dict(cur.fetchone())))


def _analyze_document(payload: dict) -> dict:
    """Read uploaded text and suggest a title + category for the trustee to confirm."""
    content = payload.get("content", "")
    filename = payload.get("filename", "")
    if not content.strip():
        raise ApiError(400, "The document appears to be empty")
    meta = llm.get_llm().suggest_metadata(content=content, filename=filename)
    chunks = rag.chunk_document(meta["title"], content)
    return {
        "title": meta["title"],
        "category": meta["category"],
        "effective_date": db.now_iso()[:10],
        "char_count": len(content),
        "chunk_count": len(chunks),
        "preview": content.strip()[:400],
        "llm": llm.provider_name(),
    }


def _ask(payload: dict) -> dict:
    question = payload.get("question", "")
    hits = rag.search(question, limit=5)
    answer = llm.get_llm().answer_question(question=question, context=[h.snippet for h in hits])
    sources = [Source(title=h.title, snippet=h.snippet[:240], kind=h.kind) for h in hits]
    return to_dict(AskOut(answer=answer, sources=sources))


def _list_drafts(query: dict) -> list:
    status = query.get("status", [None])[0]
    return [to_dict(d) for d in drafting.list_drafts(status)]


def _receive_email(payload: dict) -> dict:
    email = EmailIn(
        sender=payload["sender"],
        subject=payload["subject"],
        body=payload["body"],
        from_unit=payload.get("from_unit", payload.get("unit", "")),
    )
    # A chairman "TASK:"/"TODO:" email spawns a board task directly (no reply).
    if intake.is_task_email(email.sender, email.subject):
        return {"kind": "task", "ticket": to_dict(drafting.create_task_from_email(email))}
    return {"kind": "draft", "draft": to_dict(drafting.process_inbound(email))}


def _get_draft(draft_id: int) -> dict:
    draft = drafting.get_draft(draft_id)
    if draft is None:
        raise ApiError(404, "Draft not found")
    return to_dict(draft)


def _edit_draft(draft_id: int, payload: dict) -> dict:
    draft = drafting.edit_draft(draft_id, payload.get("body", ""))
    if draft is None:
        raise ApiError(404, "Draft not found")
    return to_dict(draft)


def _approve_draft(draft_id: int, payload: dict) -> dict:
    try:
        body = payload.get("body")
        return to_dict(drafting.approve_draft(draft_id, body))
    except KeyError as exc:
        raise ApiError(404, "Draft not found") from exc
    except drafting.GuardrailBlocked as exc:
        raise ApiError(409, str(exc)) from exc


def _discard_draft(draft_id: int) -> dict:
    draft = drafting.discard_draft(draft_id)
    if draft is None:
        raise ApiError(404, "Draft not found")
    return to_dict(draft)


def _list_tickets() -> list:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets ORDER BY id DESC")
        return [to_dict(Ticket(**dict(r))) for r in cur.fetchall()]


def _set_ticket_status(ticket_id: int, payload: dict) -> dict:
    status = payload.get("status")
    if status not in {"todo", "in_progress", "done"}:
        raise ApiError(400, "Invalid status")
    with db.cursor() as cur:
        cur.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
    if row is None:
        raise ApiError(404, "Ticket not found")
    return to_dict(Ticket(**dict(row)))


def _create_ticket(payload: dict) -> dict:
    """Raise a standalone task (manual entry, or carried from a resolution)."""
    try:
        ticket = drafting.create_task(
            title=payload.get("title", ""),
            type=payload.get("type", "general"),
            priority=payload.get("priority", "normal"),
            unit=payload.get("unit", ""),
            due_date=payload.get("due_date", ""),
            description=payload.get("description", ""),
            source=payload.get("source", "manual"),
            source_resolution_id=payload.get("source_resolution_id"),
        )
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    return to_dict(ticket)


def _list_resolutions() -> list:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM resolutions ORDER BY id DESC")
        return [
            to_dict(
                Resolution(
                    id=r["id"],
                    title=r["title"],
                    effective_date=r["effective_date"],
                    signed=bool(r["signed"]),
                    summary=r["summary"],
                    keywords=r["keywords"],
                    unit=r["unit"],
                )
            )
            for r in cur.fetchall()
        ]


# ── Specialist agent assist ──────────────────────────────────────────────────
def _assist_config() -> dict:
    """Global enable flag, kill-switch, model tiers and capability manifest."""
    return {
        "enabled": config.RUNTIME["assist_enabled"],
        "kill_switch": config.RUNTIME["kill_switch"],
        "available": config.assist_available(),
        "model_tiers": {
            tier: {"label": spec["label"], "cost_per_run": spec["cost_per_run"]}
            for tier, spec in config.MODEL_TIERS.items()
        },
        "capabilities": config.CAPABILITIES,
    }


def _set_assist_config(payload: dict) -> dict:
    """Flip the global enable flag and/or the kill-switch (cost control)."""
    if "enabled" in payload:
        config.RUNTIME["assist_enabled"] = bool(payload["enabled"])
    if "kill_switch" in payload:
        config.RUNTIME["kill_switch"] = bool(payload["kill_switch"])
    return _assist_config()


def _run_assist(ticket_id: int) -> dict:
    """Human clicked 'Get agent help' on a task — run the specialist team once."""
    try:
        run = specialists.run_assist(ticket_id)
    except specialists.AssistDisabled as exc:
        raise ApiError(409, str(exc)) from exc
    except ValueError as exc:
        raise ApiError(404, str(exc)) from exc
    return to_dict(run)


def _list_assist(ticket_id: int) -> list:
    return [to_dict(r) for r in specialists.list_runs(ticket_id)]


def _send_artifact(run_id: int, payload: dict) -> dict:
    """Human clicked Send on a drafted reply (prototype: simulated send)."""
    idx = payload.get("artifact_index")
    if not isinstance(idx, int):
        raise ApiError(400, "artifact_index (int) required")
    edited = payload.get("body")
    edited = edited if isinstance(edited, str) else None
    try:
        run = specialists.send_artifact(run_id, idx, edited)
    except specialists.SendBlocked as exc:
        raise ApiError(409, str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    return to_dict(run)


def _ticket_threads(ticket_id: int) -> dict:
    """Related correspondence across different email threads (same matter)."""
    with db.cursor() as cur:
        cur.execute("SELECT topic_key FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
    if row is None:
        raise ApiError(404, "Ticket not found")
    topic_key = row["topic_key"]
    return {"topic_key": topic_key, "threads": threads.related_threads(topic_key)}


# ── Routing ───────────────────────────────────────────────────────────────────
_DRAFT_ID = re.compile(r"^/api/drafts/(\d+)$")
_DRAFT_APPROVE = re.compile(r"^/api/drafts/(\d+)/approve$")
_DRAFT_DISCARD = re.compile(r"^/api/drafts/(\d+)/discard$")
_TICKET_STATUS = re.compile(r"^/api/tickets/(\d+)/status$")
_TICKET_ASSIST = re.compile(r"^/api/tickets/(\d+)/assist$")
_TICKET_THREADS = re.compile(r"^/api/tickets/(\d+)/threads$")
_ASSIST_SEND = re.compile(r"^/api/assist/(\d+)/send$")


class Handler(BaseHTTPRequestHandler):
    server_version = "STAPPrototype/0.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        # Quieter console: only log API calls. args[0] may be an int (e.g. from
        # send_error's "code %d, message %s"), so guard the membership test.
        first = args[0] if args else ""
        if isinstance(first, str) and "/api/" in first:
            super().log_message(fmt, *args)

    # -- helpers --
    def _send_json(self, obj: object, status: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError as exc:
            raise ApiError(400, "Invalid JSON body") from exc

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (config.WEB_DIR / rel).resolve()
        web_root = config.WEB_DIR.resolve()
        if web_root not in target.parents and target != web_root:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "content-type", _STATIC_TYPES.get(target.suffix, "application/octet-stream")
        )
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- verbs --
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/api/health":
                return self._send_json(_health())
            if path == "/api/documents":
                return self._send_json(_list_documents())
            if path == "/api/drafts":
                return self._send_json(_list_drafts(query))
            if path == "/api/tickets":
                return self._send_json(_list_tickets())
            if path == "/api/resolutions":
                return self._send_json(_list_resolutions())
            if path == "/api/assist/config":
                return self._send_json(_assist_config())
            m = _TICKET_ASSIST.match(path)
            if m:
                return self._send_json(_list_assist(int(m.group(1))))
            m = _TICKET_THREADS.match(path)
            if m:
                return self._send_json(_ticket_threads(int(m.group(1))))
            m = _DRAFT_ID.match(path)
            if m:
                return self._send_json(_get_draft(int(m.group(1))))
            if path.startswith("/api/"):
                raise ApiError(404, "Not found")
            return self._serve_static(path)
        except ApiError as exc:
            self._send_json({"detail": exc.detail}, exc.status)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/seed":
                return self._send_json(_reseed())
            if path == "/api/documents/analyze":
                return self._send_json(_analyze_document(payload))
            if path == "/api/documents":
                return self._send_json(_add_document(payload))
            if path == "/api/ask":
                return self._send_json(_ask(payload))
            if path == "/api/inbox":
                return self._send_json(_receive_email(payload))
            if path == "/api/tickets":
                return self._send_json(_create_ticket(payload))
            m = _DRAFT_APPROVE.match(path)
            if m:
                return self._send_json(_approve_draft(int(m.group(1)), payload))
            m = _DRAFT_DISCARD.match(path)
            if m:
                return self._send_json(_discard_draft(int(m.group(1))))
            m = _TICKET_STATUS.match(path)
            if m:
                return self._send_json(_set_ticket_status(int(m.group(1)), payload))
            if path == "/api/assist/config":
                return self._send_json(_set_assist_config(payload))
            m = _TICKET_ASSIST.match(path)
            if m:
                return self._send_json(_run_assist(int(m.group(1))))
            m = _ASSIST_SEND.match(path)
            if m:
                return self._send_json(_send_artifact(int(m.group(1)), payload))
            raise ApiError(404, "Not found")
        except ApiError as exc:
            self._send_json({"detail": exc.detail}, exc.status)

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            m = _DRAFT_ID.match(path)
            if m:
                return self._send_json(_edit_draft(int(m.group(1)), payload))
            raise ApiError(404, "Not found")
        except ApiError as exc:
            self._send_json({"detail": exc.detail}, exc.status)


def _bootstrap() -> None:
    db.init_db()
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM documents")
        empty = cur.fetchone()["n"] == 0
    if empty:
        from .seed import seed

        seed()


def main() -> None:
    import os

    _bootstrap()
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"▸ Trustee Platform prototype on http://localhost:{port}  (llm: {llm.provider_name()})")
    print("  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n▸ Stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
