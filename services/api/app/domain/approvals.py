"""Signed approval magic-links — stateless HMAC tokens.

A feature request is approved by clicking a link emailed to the approver. The
link carries a compact, HMAC-signed token holding the request claims + an expiry
so the API needs no server-side state to validate it. Tampering breaks the
signature; replay is bounded by ``exp``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class ApprovalError(RuntimeError):
    """Raised when a token is malformed, tampered with, or expired."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64encode(digest)


def make_token(
    *, secret: str, claims: dict[str, Any], ttl_seconds: int, now: float | None = None
) -> str:
    """Return ``<payload>.<signature>`` for ``claims`` valid for ``ttl_seconds``."""
    if not secret:
        raise ApprovalError("an approval secret is required to sign tokens.")
    issued = int(now if now is not None else time.time())
    body = {**claims, "exp": issued + ttl_seconds}
    payload = _b64encode(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(secret, payload)}"


def read_token(*, secret: str, token: str, now: float | None = None) -> dict[str, Any]:
    """Validate the signature + expiry and return the claims, else raise."""
    if not secret:
        raise ApprovalError("an approval secret is required to verify tokens.")
    payload, _, signature = token.partition(".")
    if not payload or not signature:
        raise ApprovalError("malformed token.")
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        raise ApprovalError("bad signature.")
    try:
        claims: dict[str, Any] = json.loads(_b64decode(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ApprovalError("undecodable token payload.") from exc
    current = int(now if now is not None else time.time())
    if int(claims.get("exp", 0)) < current:
        raise ApprovalError("token has expired.")
    return claims
