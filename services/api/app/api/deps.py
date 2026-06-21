"""FastAPI dependencies — resolve the per-request ports from app state."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.ports.llm import LLM
from app.ports.repository import Repository
from app.settings import Settings, get_settings


def get_repo(request: Request) -> Repository:
    repo: Repository = request.app.state.repo
    return repo


def get_llm(request: Request) -> LLM:
    llm: LLM = request.app.state.llm
    return llm


RepoDep = Annotated[Repository, Depends(get_repo)]
LLMDep = Annotated[LLM, Depends(get_llm)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
