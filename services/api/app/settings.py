"""Runtime configuration — environment-driven (12-factor).

Replaces the prototype's `config.py`. Every value can be overridden by an
environment variable prefixed ``STAK_`` so the same image runs locally, in CI,
and on Lambda without code changes.

Nothing here reaches out to AWS; the adapters read these settings to decide
which backend to use.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["stub", "anthropic", "bedrock"]
RepoBackend = Literal["sqlite", "dynamodb"]

_SERVICE_DIR = Path(__file__).resolve().parent.parent


class ModelTier(BaseSettings):
    """A reasoning tier the orchestrator can select by task complexity."""

    label: str
    bedrock_id: str
    cost_per_run: float


class Settings(BaseSettings):
    """Application settings, hydrated from the environment (prefix ``STAK_``)."""

    model_config = SettingsConfigDict(
        env_prefix="STAK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Identity / governance ────────────────────────────────────────────────
    accountable_human: str = "Chairperson"
    # Addresses allowed to spawn board tasks via a "TASK:" / "TODO:" email.
    chairman_emails: frozenset[str] = frozenset(
        {"trustee.chair@gmail.com", "chair@acaciaheights.co.za"}
    )

    # ── Persistence ──────────────────────────────────────────────────────────
    repo_backend: RepoBackend = "sqlite"
    # Local SQLite location (dev only). DynamoDB uses table names instead.
    data_dir: Path = _SERVICE_DIR / "data"
    sqlite_filename: str = "app.db"
    dynamo_table: str = "stak-platform"

    # ── LLM provider ─────────────────────────────────────────────────────────
    llm_provider: Provider = "stub"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    aws_region: str = "af-south-1"
    # Cross-region inference target when Bedrock Claude is absent in af-south-1
    # (SOLUTION_DESIGN §4.2). Empty = call in `aws_region`.
    bedrock_inference_region: str = "eu-west-1"

    # ── Agent-assist runtime flags (kill-switch + global toggle) ─────────────
    assist_enabled: bool = True
    assist_kill_switch: bool = False

    # ── Web (static dashboard) ───────────────────────────────────────────────
    # Served only in local/dev; in production CloudFront + S3 host the SPA.
    serve_static: bool = True
    web_dir: Path = _SERVICE_DIR.parent.parent / "prototype" / "web"

    # ── CORS (dashboard origin) ──────────────────────────────────────────────
    cors_allow_origins: tuple[str, ...] = ("http://localhost:8000",)

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.sqlite_filename

    @property
    def model_tiers(self) -> dict[str, ModelTier]:
        """Bedrock model tiers (cost-aware) — fast/balanced/deep."""
        return {
            "fast": ModelTier(
                label="Claude 3 Haiku",
                bedrock_id="anthropic.claude-3-haiku-20240307-v1:0",
                cost_per_run=0.01,
            ),
            "balanced": ModelTier(
                label="Claude 3.5 Sonnet",
                bedrock_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                cost_per_run=0.08,
            ),
            "deep": ModelTier(
                label="Claude 3 Opus",
                bedrock_id="anthropic.claude-3-opus-20240229-v1:0",
                cost_per_run=0.33,
            ),
        }

    def resolve_provider(self) -> Provider:
        """Auto-detect Anthropic when a key is present but provider left default."""
        if self.llm_provider == "stub" and self.anthropic_api_key:
            return "anthropic"
        return self.llm_provider

    def assist_available(self) -> bool:
        return self.assist_enabled and not self.assist_kill_switch

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Read/draft/compute capabilities the agent assist is allowed to use. Anything
# outside this allow-list must be proposed as a new governed tool, never acted on.
CAPABILITIES: dict[str, tuple[str, ...]] = {
    "read": ("document_brain", "resolution_register", "interaction_ledger", "ticket"),
    "draft": (
        "resolution_template",
        "correspondence",
        "action_plan",
        "research_brief",
        "owner_circular",
    ),
    "compute": ("levy_interest", "reserve_projection", "budget_model", "quote_comparison"),
}


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — FastAPI depends on this so tests can override it."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
