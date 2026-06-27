"""Unit tests for the signed approval magic-link tokens. Pure, no I/O."""

from __future__ import annotations

import pytest
from app.domain.approvals import ApprovalError, make_token, read_token

_SECRET = "unit-test-key"  # pragma: allowlist secret


def test_round_trip_returns_claims() -> None:
    token = make_token(
        secret=_SECRET,
        claims={"title": "Dark mode", "requester": "trustee"},
        ttl_seconds=60,
        now=1000,
    )
    claims = read_token(secret=_SECRET, token=token, now=1000)
    assert claims["title"] == "Dark mode"
    assert claims["requester"] == "trustee"
    assert claims["exp"] == 1060


def test_make_token_requires_a_secret() -> None:
    with pytest.raises(ApprovalError):
        make_token(secret="", claims={}, ttl_seconds=60)


def test_read_token_requires_a_secret() -> None:
    with pytest.raises(ApprovalError):
        read_token(secret="", token="a.b")


def test_tampered_payload_fails_signature() -> None:
    token = make_token(secret=_SECRET, claims={"title": "x"}, ttl_seconds=60, now=1000)
    payload, _, signature = token.partition(".")
    forged = f"{payload}AAAA.{signature}"
    with pytest.raises(ApprovalError):
        read_token(secret=_SECRET, token=forged, now=1000)


def test_wrong_secret_fails_signature() -> None:
    token = make_token(secret=_SECRET, claims={"title": "x"}, ttl_seconds=60, now=1000)
    with pytest.raises(ApprovalError):
        read_token(secret="other-key", token=token, now=1000)  # pragma: allowlist secret


def test_malformed_token_rejected() -> None:
    with pytest.raises(ApprovalError):
        read_token(secret=_SECRET, token="no-dot-here", now=1000)


def test_expired_token_rejected() -> None:
    token = make_token(secret=_SECRET, claims={"title": "x"}, ttl_seconds=60, now=1000)
    with pytest.raises(ApprovalError):
        read_token(secret=_SECRET, token=token, now=2000)


def test_undecodable_payload_rejected() -> None:
    # A correctly-signed but non-JSON payload still fails to decode.
    from app.domain.approvals import _sign

    payload = "not-base64-json"
    token = f"{payload}.{_sign(_SECRET, payload)}"
    with pytest.raises(ApprovalError):
        read_token(secret=_SECRET, token=token, now=1000)
