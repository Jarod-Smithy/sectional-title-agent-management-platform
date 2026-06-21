"""Application factory + Lambda handler.

Local/dev: ``uvicorn app.main:app`` serves the API and the static dashboard.
AWS: API Gateway invokes ``app.main.handler`` (Mangum adapter) — same app, no
code change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from app import __version__
from app.api.routes import router
from app.bootstrap import build_llm, build_repo
from app.domain import seed as seed_module
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    repo = build_repo(settings)
    llm = build_llm(settings)
    app.state.repo = repo
    app.state.llm = llm
    app.state.runtime = {
        "assist_enabled": settings.assist_enabled,
        "kill_switch": settings.assist_kill_switch,
    }
    # First-run convenience: seed the sample scheme if the store is empty.
    if repo.count_documents() == 0:
        seed_module.seed(repo, llm)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Trustee Platform — Dashboard API",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    # Serve the static dashboard locally (in production CloudFront + S3 host it).
    if settings.serve_static and settings.web_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.web_dir, html=True),
            name="dashboard",
        )
    return app


app = create_app()
handler = Mangum(app)
