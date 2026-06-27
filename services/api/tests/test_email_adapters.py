"""Unit tests for the email adapters + the email composition root.

No network: the SES sender takes an INJECTED fake boto3 ``ses`` client (the same
pattern as the Bedrock adapter tests), so SendEmail params are asserted exactly.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from app.adapters.ses_email import LogEmailSender, SesEmailSender
from app.bootstrap import build_email_sender
from app.ports.email import EmailError
from app.settings import Settings


class _FakeSes:
    """Stands in for the boto3 ``ses`` client."""

    def __init__(self, *, message_id: str | None = "ses-msg-1", raises: bool = False) -> None:
        self._message_id = message_id
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("ses throttled")
        if self._message_id is None:
            return {}
        return {"MessageId": self._message_id}


# ── LogEmailSender (dev no-op) ───────────────────────────────────────────────
def test_log_sender_records_but_never_sends(caplog: pytest.LogCaptureFixture) -> None:
    sender = LogEmailSender(sender="from@scheme.co.za")
    with caplog.at_level(logging.INFO, logger="stak.email"):
        result = sender.send(to="owner@example.com", subject="Hi", body="Body text")
    assert result == "log:not-sent"
    assert "owner@example.com" in caplog.text


# ── SesEmailSender ────────────────────────────────────────────────────────────
def test_ses_sender_requires_a_from_address() -> None:
    with pytest.raises(EmailError):
        SesEmailSender(client=_FakeSes(), sender="")


def test_ses_sender_sends_and_returns_message_id() -> None:
    client = _FakeSes(message_id="abc-123")
    sender = SesEmailSender(client=client, sender="from@scheme.co.za")
    message_id = sender.send(to="owner@example.com", subject="RE: Leak", body="Noted.")
    assert message_id == "abc-123"
    params = client.calls[0]
    assert params["Source"] == "from@scheme.co.za"
    assert params["Destination"] == {"ToAddresses": ["owner@example.com"]}
    assert params["Message"]["Subject"]["Data"] == "RE: Leak"
    assert params["Message"]["Body"]["Text"]["Data"] == "Noted."


def test_ses_sender_wraps_client_error() -> None:
    sender = SesEmailSender(client=_FakeSes(raises=True), sender="from@scheme.co.za")
    with pytest.raises(EmailError):
        sender.send(to="owner@example.com", subject="s", body="b")


def test_ses_sender_rejects_missing_message_id() -> None:
    sender = SesEmailSender(client=_FakeSes(message_id=None), sender="from@scheme.co.za")
    with pytest.raises(EmailError):
        sender.send(to="owner@example.com", subject="s", body="b")


# ── Composition root ─────────────────────────────────────────────────────────
def test_build_email_sender_defaults_to_log() -> None:
    sender = build_email_sender(Settings(email_provider="log"))
    assert isinstance(sender, LogEmailSender)


def test_build_email_sender_returns_ses_when_configured() -> None:
    sender = build_email_sender(
        Settings(email_provider="ses", email_from="from@scheme.co.za", email_region="af-south-1")
    )
    assert isinstance(sender, SesEmailSender)


# ── Settings seams ────────────────────────────────────────────────────────────
def test_email_resolved_region_prefers_explicit_then_falls_back() -> None:
    assert Settings(email_region="eu-west-1").email_resolved_region == "eu-west-1"
    assert Settings(email_region="", aws_region="af-south-1").email_resolved_region == "af-south-1"
