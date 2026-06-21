"""FastAPI dependencies — resolve the per-request ports from app state."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.ports.llm import LLM
from app.ports.repository import Repository
from app.security import CognitoVerifier, InvalidToken, Principal
from app.settings import Settings, get_settings


def get_repo(request: Request) -> Repository:
    repo: Repository = request.app.state.repo
    return repo


def get_llm(request: Request) -> LLM:
    llm: LLM = request.app.state.llm
    return llm


# Synthetic caller used when auth is disabled (local/dev/CI). Keeps handlers
# that depend on the principal working without a real token.
_DEV_PRINCIPAL = Principal(subject="dev", username="dev", groups=("trustee",))


def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """Authenticate the caller from the ``Authorization: Bearer`` header.

    When ``auth_enabled`` is off this returns a synthetic dev principal so the
    API stays open for local development and the existing test-suite. When on,
    a valid Cognito access token is required.
    """
    if not settings.auth_enabled:
        return _DEV_PRINCIPAL

    verifier: CognitoVerifier | None = getattr(request.app.state, "verifier", None)
    if verifier is None:  # misconfiguration: enabled but no pool wired in
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is enabled but not configured",
        )

    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verifier.verify(token.strip())
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


RepoDep = Annotated[Repository, Depends(get_repo)]
LLMDep = Annotated[LLM, Depends(get_llm)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[Principal, Depends(get_current_user)]
