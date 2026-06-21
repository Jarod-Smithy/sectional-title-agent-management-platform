"""Cognito JWT verification + route-protection tests.

Self-contained: an in-process RSA keypair signs access tokens, and a stub JWK
client feeds the matching public key to the verifier — no network, no real
Cognito pool.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from app.security import CognitoVerifier, InvalidToken
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi.testclient import TestClient

ISSUER = "https://cognito-idp.af-south-1.amazonaws.com/af-south-1_testpool"
CLIENT_ID = "test-client-id"


def _make_token(private_key: RSAPrivateKey, **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-1",
        "username": "jarod",
        "token_use": "access",
        "client_id": CLIENT_ID,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
        "cognito:groups": ["trustee"],
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


class _StubJWKClient:
    """Returns a fixed public key regardless of the token's kid."""

    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self._public_key)


@pytest.fixture(scope="module")
def keypair() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def verifier(keypair: RSAPrivateKey) -> CognitoVerifier:
    return CognitoVerifier(
        jwks_url="https://example.invalid/jwks.json",
        issuer=ISSUER,
        client_id=CLIENT_ID,
        jwk_client=_StubJWKClient(keypair.public_key()),
    )


# ── Unit: verifier ────────────────────────────────────────────────────────────
def test_valid_token_returns_principal(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    principal = verifier.verify(_make_token(keypair))
    assert principal.subject == "user-1"
    assert principal.username == "jarod"
    assert principal.groups == ("trustee",)
    assert principal.claims["client_id"] == CLIENT_ID


def test_expired_token_rejected(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    past = int(time.time()) - 10
    token = _make_token(keypair, iat=past - 3600, exp=past)
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_wrong_issuer_rejected(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    token = _make_token(keypair, iss="https://evil.example.com/pool")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_id_token_rejected(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    token = _make_token(keypair, token_use="id")  # noqa: S106 - test claim, not a secret
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_wrong_client_id_rejected(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    token = _make_token(keypair, client_id="someone-else")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_missing_sub_rejected(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    token = _make_token(keypair, sub="")
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_bad_signature_rejected(verifier: CognitoVerifier) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(other_key)
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_non_list_groups_yields_empty(verifier: CognitoVerifier, keypair: RSAPrivateKey) -> None:
    token = _make_token(keypair, **{"cognito:groups": "trustee"})
    principal = verifier.verify(token)
    assert principal.groups == ()


# ── Integration: route protection when auth is enabled ────────────────────────
@pytest.fixture
def auth_client(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
    keypair: RSAPrivateKey,
) -> Iterator[TestClient]:
    monkeypatch.setenv("STAK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAK_SERVE_STATIC", "false")
    monkeypatch.setenv("STAK_REPO_BACKEND", "sqlite")
    monkeypatch.setenv("STAK_LLM_PROVIDER", "stub")
    monkeypatch.setenv("STAK_AUTH_ENABLED", "true")
    monkeypatch.setenv("STAK_COGNITO_USER_POOL_ID", "af-south-1_testpool")
    monkeypatch.setenv("STAK_COGNITO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("STAK_COGNITO_REGION", "af-south-1")

    from app.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        # Swap the lazily-built verifier for one wired to the in-test keypair.
        app.state.verifier = CognitoVerifier(
            jwks_url="https://example.invalid/jwks.json",
            issuer=ISSUER,
            client_id=CLIENT_ID,
            jwk_client=_StubJWKClient(keypair.public_key()),
        )
        yield test_client
    get_settings.cache_clear()


def test_health_is_public_when_auth_enabled(auth_client: TestClient) -> None:
    assert auth_client.get("/api/health").status_code == 200


def test_protected_route_requires_token(auth_client: TestClient) -> None:
    resp = auth_client.get("/api/documents")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_protected_route_rejects_garbage_token(auth_client: TestClient) -> None:
    resp = auth_client.get("/api/documents", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_protected_route_accepts_valid_token(
    auth_client: TestClient, keypair: RSAPrivateKey
) -> None:
    token = _make_token(keypair)
    resp = auth_client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_auth_disabled_allows_anonymous(client: TestClient) -> None:
    # The default `client` fixture has auth off → protected routes stay open.
    assert client.get("/api/documents").status_code == 200


def test_enabled_but_unconfigured_returns_503(auth_client: TestClient) -> None:
    # Auth on but no verifier wired (misconfiguration) → fail closed, not open.
    auth_client.app.state.verifier = None  # type: ignore[attr-defined]
    resp = auth_client.get("/api/documents", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 503
