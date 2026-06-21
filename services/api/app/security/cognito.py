"""Cognito access-token verification (RS256 against the pool's public JWKS).

The API trusts AWS Cognito to authenticate users. Clients present the Cognito
**access token** as ``Authorization: Bearer <jwt>``; this module verifies the
signature against the user pool's published public keys and checks the standard
claims (issuer, expiry, ``token_use``, ``client_id``). No AWS credentials or
network calls to Cognito's API are needed — only an HTTPS fetch of the public
JWKS document, which PyJWT caches.

Verification is intentionally a thin, dependency-light seam: ``auth_enabled`` is
off by default (see :class:`app.settings.Settings`), so local/dev/CI never touch
this code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt


class InvalidToken(Exception):
    """Raised when a presented token fails verification."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller derived from a verified access token."""

    subject: str
    username: str
    groups: tuple[str, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)


class _SigningKey(Protocol):
    key: Any


class _JWKClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> _SigningKey: ...


class CognitoVerifier:
    """Verify Cognito access tokens against a user pool's public JWKS.

    Parameters
    ----------
    jwks_url:
        The ``.../.well-known/jwks.json`` endpoint for the user pool.
    issuer:
        Expected ``iss`` claim (the pool's issuer URL).
    client_id:
        Expected ``client_id`` claim (the app client). Empty disables the check.
    jwk_client:
        Optional injected signing-key resolver (used in tests). Defaults to a
        :class:`jwt.PyJWKClient`, which fetches and caches the JWKS lazily.
    """

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        client_id: str,
        jwk_client: _JWKClient | None = None,
    ) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._jwk_client: _JWKClient = jwk_client or jwt.PyJWKClient(jwks_url)

    def verify(self, token: str) -> Principal:
        """Return the :class:`Principal` for a valid token, else raise.

        Raises
        ------
        InvalidToken
            If the signature, issuer, expiry, ``token_use`` or ``client_id`` is
            invalid.
        """
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"verify_aud": False, "require": ["exp", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - JWKS fetch / key errors
            raise InvalidToken(f"signing key resolution failed: {exc}") from exc

        if claims.get("token_use") != "access":
            raise InvalidToken("expected a Cognito access token")
        if self._client_id and claims.get("client_id") != self._client_id:
            raise InvalidToken("client_id does not match the configured app client")

        subject = str(claims.get("sub", ""))
        if not subject:
            raise InvalidToken("token is missing the 'sub' claim")
        raw_groups = claims.get("cognito:groups", [])
        groups = tuple(str(g) for g in raw_groups) if isinstance(raw_groups, list) else ()
        return Principal(
            subject=subject,
            username=str(claims.get("username", subject)),
            groups=groups,
            claims=claims,
        )
