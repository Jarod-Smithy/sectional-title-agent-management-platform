"""Composition root — builds concrete adapters from settings and wires them.

This is the only module that imports concrete adapters. The API and domain
layers depend on the ports, not on these constructors.
"""

from __future__ import annotations

from app.adapters.sqlite_repo import SqliteRepository
from app.adapters.stub_llm import StubLLM
from app.ports.llm import LLM
from app.ports.repository import Repository
from app.settings import Settings


def build_repo(settings: Settings) -> Repository:
    if settings.repo_backend == "sqlite":
        settings.ensure_dirs()
        repo = SqliteRepository(settings.db_path)
        repo.init()
        return repo
    # DynamoDB adapter lands in Increment 6.
    raise NotImplementedError(f"repo_backend '{settings.repo_backend}' not yet implemented")


def build_llm(settings: Settings) -> LLM:
    provider = settings.resolve_provider()
    if provider == "stub":
        return StubLLM(accountable_human=settings.accountable_human)
    # Anthropic / Bedrock adapters land in Increment 7; fall back to the stub so
    # the service still runs if a provider is selected before its adapter exists.
    return StubLLM(accountable_human=settings.accountable_human)
