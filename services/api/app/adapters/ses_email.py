"""Email adapters — the offline ``log`` no-op and the Amazon SES sender.

Both implement :class:`app.ports.email.EmailSender`. The composition root
(:mod:`app.bootstrap`) selects one from ``STAK_EMAIL_PROVIDER``; the domain only
ever sees the Protocol.

Design notes:
* ``LogEmailSender`` performs NO network I/O — it logs and returns a synthetic
  ``log:`` message id. It is the dev/CI default so the suite never sends mail.
* ``SesEmailSender`` takes an INJECTED boto3 ``ses`` client (a tiny Protocol),
  so this module imports no AWS SDK and stays trivially unit-testable. The real
  client is built only when ``STAK_EMAIL_PROVIDER=ses``.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.ports.email import EmailError

logger = logging.getLogger("stak.email")


class _SesClient(Protocol):
    """The single boto3 ``ses`` method this adapter needs."""

    def send_email(self, **kwargs: Any) -> dict[str, Any]: ...


class LogEmailSender:
    """Dev-safe no-op sender: records the would-be email and never sends."""

    def __init__(self, *, sender: str = "") -> None:
        self._sender = sender

    def send(self, *, to: str, subject: str, body: str) -> str:
        logger.info(
            "email.log from=%s to=%s subject=%s chars=%d (not sent — log provider)",
            self._sender or "<unset>",
            to,
            subject,
            len(body),
        )
        return "log:not-sent"


class SesEmailSender:
    """Sends plain-text email through Amazon SES ``SendEmail``."""

    def __init__(self, *, client: _SesClient, sender: str) -> None:
        if not sender:
            raise EmailError("SES sender (email_from) is required when email_provider='ses'.")
        self._client = client
        self._sender = sender

    def send(self, *, to: str, subject: str, body: str) -> str:
        try:
            resp = self._client.send_email(
                Source=self._sender,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )
        except Exception as exc:
            raise EmailError(f"SES send_email failed: {exc}") from exc
        message_id = resp.get("MessageId")
        if not isinstance(message_id, str) or not message_id:
            raise EmailError("SES send_email returned no MessageId.")
        return message_id
