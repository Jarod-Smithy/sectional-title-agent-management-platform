"""Email port — the single seam to outbound correspondence delivery.

The drafting flow records every reply in the interaction ledger (the system of
record). When a real provider is configured it ALSO delivers the reply through
this seam. ``LogEmailSender`` (dev default) is an offline no-op that only logs;
``SesEmailSender`` sends through Amazon SES. Domain code depends on this
Protocol, never on a concrete adapter.
"""

from __future__ import annotations

from typing import Protocol


class EmailError(RuntimeError):
    """Raised when delivery fails or a provider returns an unusable response."""


class EmailSender(Protocol):
    """Deliver an outbound email and return a provider message id."""

    def send(self, *, to: str, subject: str, body: str) -> str: ...
