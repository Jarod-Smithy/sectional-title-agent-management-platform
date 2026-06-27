"""Tests for the drafting → email-delivery seam.

``_send_reply_email`` resolves a recipient and best-effort delivers an approved
or auto-filed reply; the interaction ledger is the system of record, so any
delivery failure is swallowed. The integration cases prove a configured SES
provider actually sends, while the ``log`` provider only files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.ses_email import LogEmailSender, SesEmailSender
from app.adapters.sqlite_repo import SqliteRepository
from app.adapters.stub_llm import StubLLM
from app.domain import drafting
from app.ports.email import EmailError
from app.ports.repository import Repository
from app.schemas import Draft, EmailIn


class _SpySender:
    """Records every delivered email; can simulate a provider failure."""

    def __init__(self, *, raises: bool = False) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self._raises = raises

    def send(self, *, to: str, subject: str, body: str) -> str:
        if self._raises:
            raise EmailError("provider down")
        self.sent.append((to, subject, body))
        return "spy-msg-1"


class _FakeSes:
    """Stands in for the boto3 ``ses`` client (used through ``SesEmailSender``)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"MessageId": "ses-1"}


def _draft(*, party: str, body: str = "Dear Owner, noted. Regards.") -> Draft:
    return Draft(
        id=7,
        interaction_id=1,
        intent="maintenance",
        party=party,
        from_unit="",
        unit="Unit 4",
        case_ref="MAI-4-X",
        priority="normal",
        inbound_subject="Leak",
        inbound_snippet="there is a leak",
        body=body,
        status="pending",
        auto_send_eligible=False,
    )


def _repo(tmp_path: Path) -> Repository:
    repo = SqliteRepository(tmp_path / "drafting.db")
    repo.init()
    return repo


# ── _send_reply_email branches ───────────────────────────────────────────────
def test_send_reply_email_no_sender_is_noop() -> None:
    # Must not raise when no provider is configured.
    drafting._send_reply_email(None, _draft(party="Jane Doe"), reply_to="owner@example.com")


def test_send_reply_email_uses_reply_to_address() -> None:
    spy = _SpySender()
    drafting._send_reply_email(spy, _draft(party="Jane Doe"), reply_to="owner@example.com")
    assert spy.sent[0][0] == "owner@example.com"
    assert spy.sent[0][1].startswith("RE: ")


def test_send_reply_email_falls_back_to_party_email() -> None:
    spy = _SpySender()
    drafting._send_reply_email(spy, _draft(party="owner@example.com"), reply_to=None)
    assert spy.sent[0][0] == "owner@example.com"


def test_send_reply_email_skips_when_no_resolvable_recipient() -> None:
    spy = _SpySender()
    drafting._send_reply_email(spy, _draft(party="Jane Doe"), reply_to=None)
    assert spy.sent == []


def test_send_reply_email_swallows_provider_error() -> None:
    spy = _SpySender(raises=True)
    # A delivery failure must not propagate (ledger already recorded the reply).
    drafting._send_reply_email(spy, _draft(party="Jane Doe"), reply_to="owner@example.com")
    assert spy.sent == []


# ── Integration: process_inbound auto-send + approve_draft ───────────────────
def test_acknowledgement_auto_send_delivers_via_ses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    llm = StubLLM(accountable_human="Chair")
    fake = _FakeSes()
    ses = SesEmailSender(client=fake, sender="trustees@scheme.co.za")
    draft = drafting.process_inbound(
        repo,
        llm,
        EmailIn(sender="owner@example.com", subject="Thanks!", body="Thank you, appreciated."),
        email_sender=ses,
    )
    assert draft.status == "auto_filed"
    assert fake.calls[0]["Destination"] == {"ToAddresses": ["owner@example.com"]}


def test_acknowledgement_auto_send_log_provider_only_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    llm = StubLLM(accountable_human="Chair")
    draft = drafting.process_inbound(
        repo,
        llm,
        EmailIn(sender="owner@example.com", subject="Thanks!", body="Thank you, appreciated."),
        email_sender=LogEmailSender(sender="trustees@scheme.co.za"),
    )
    # Filed, but the log provider performed no network send.
    assert draft.status == "auto_filed"


def test_approve_draft_files_and_raises_ticket_with_sender(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    llm = StubLLM(accountable_human="Chair")
    pending = drafting.process_inbound(
        repo,
        llm,
        EmailIn(sender="jane.doe@example.com", subject="Leak in Unit 9", body="A leak in unit 9."),
    )
    assert pending.status == "pending"
    spy = _SpySender()
    approved = drafting.approve_draft(repo, pending.id, email_sender=spy)
    assert approved.status == "filed"
    assert any(t.case_ref == approved.case_ref for t in repo.list_tickets())
    # Party resolved to a name (not an address), so nothing is delivered.
    assert spy.sent == []
