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
EmailProvider = Literal["log", "ses"]

_SERVICE_DIR = Path(__file__).resolve().parent.parent

# Cross-region inference-profile geo prefix by region family. Claude on Bedrock
# is reached via a geo profile (e.g. ``eu.anthropic.claude-…``) outside us-east-1.
_BEDROCK_GEO: dict[str, str] = {"eu": "eu", "us": "us", "ap": "apac"}


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

    # ── Demo seeding ─────────────────────────────────────────────────────────
    # The sample "Acacia Heights" scheme is injected at cold-start (when the
    # store is empty) and via POST /api/seed. Off by default so real
    # deployments never auto-populate fake data; the dev live stack opts in
    # (STAK_SEED_ENABLED=true) to keep the demo dashboard populated.
    seed_enabled: bool = False

    # ── Outbound email (SES) ─────────────────────────────────────────────────
    # ``log`` (default) is a dev-safe no-op that only records the interaction;
    # ``ses`` actually sends approved/auto-filed replies via Amazon SES from
    # ``email_from`` in ``email_region``. SES sending IS available in
    # af-south-1. The from-identity must be verified out-of-band (manual DKIM /
    # email verification — see infra/modules/ses) before ``ses`` will deliver.
    email_provider: EmailProvider = "log"
    email_from: str = ""
    email_region: str = "af-south-1"

    # ── Document uploads (S3) ────────────────────────────────────────────────
    # When ``documents_bucket`` is empty (default) the S3 upload endpoints are
    # disabled (503) and only the paste-text path is available — dev-safe with
    # zero standing storage. Set the bucket (live stack) to enable presigned
    # uploads; ``upload_url_expiry_seconds`` bounds the presigned PUT lifetime.
    documents_bucket: str = ""
    documents_region: str = "af-south-1"
    upload_url_expiry_seconds: int = 900

    # ── LLM provider ─────────────────────────────────────────────────────────
    llm_provider: Provider = "stub"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    aws_region: str = "af-south-1"
    # Cross-region inference target when Bedrock Claude is absent in af-south-1
    # (SOLUTION_DESIGN §4.2). Empty = call in `aws_region`.
    bedrock_inference_region: str = "eu-west-1"
    # Default reasoning tier used by the Bedrock adapter (fast|balanced|deep).
    bedrock_model_tier: str = "balanced"

    # ── Agent-assist runtime flags (kill-switch + global toggle) ─────────────
    assist_enabled: bool = True
    assist_kill_switch: bool = False

    # ── Auth (Cognito JWT) ───────────────────────────────────────────────────
    # Off by default so local/dev/CI run unauthenticated; production sets
    # STAK_AUTH_ENABLED=true once the pool/client (Terraform) and a trustee user
    # exist. When enabled, every route except /api/health requires a valid
    # Cognito access token (RS256, verified against the pool's public JWKS).
    auth_enabled: bool = False
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    # Region the user pool lives in; empty falls back to ``aws_region``.
    cognito_region: str = ""

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
    def cognito_pool_region(self) -> str:
        """Region of the Cognito user pool (falls back to ``aws_region``)."""
        return self.cognito_region or self.aws_region

    @property
    def cognito_issuer(self) -> str:
        """Expected ``iss`` claim / JWKS base for the configured user pool."""
        return (
            f"https://cognito-idp.{self.cognito_pool_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}"
        )

    @property
    def cognito_jwks_url(self) -> str:
        """Public signing-key set used to verify access-token signatures."""
        return f"{self.cognito_issuer}/.well-known/jwks.json"

    @property
    def model_tiers(self) -> dict[str, ModelTier]:
        """Bedrock model tiers (cost-aware) — fast/balanced/deep.

        IDs are the base model names; ``bedrock_model_id`` prepends the
        cross-region inference-profile geo prefix (e.g. ``eu.``). Verified
        available as eu-west-1 inference profiles for this account on
        2026-06-27. ``fast`` (Haiku 4.5) additionally requires the one-time
        Anthropic use-case form to be submitted for the account.
        """
        return {
            "fast": ModelTier(
                label="Claude Haiku 4.5",
                bedrock_id="anthropic.claude-haiku-4-5-20251001-v1:0",
                cost_per_run=0.01,
            ),
            "balanced": ModelTier(
                label="Claude Sonnet 4.6",
                bedrock_id="anthropic.claude-sonnet-4-6",
                cost_per_run=0.06,
            ),
            "deep": ModelTier(
                label="Claude Opus 4.6",
                bedrock_id="anthropic.claude-opus-4-6-v1",
                cost_per_run=0.30,
            ),
        }

    @property
    def bedrock_resolved_region(self) -> str:
        """Region the Bedrock client targets (falls back to ``aws_region``)."""
        return self.bedrock_inference_region or self.aws_region

    @property
    def email_resolved_region(self) -> str:
        """Region the SES client targets (falls back to ``aws_region``)."""
        return self.email_region or self.aws_region

    @property
    def documents_resolved_region(self) -> str:
        """Region the S3 documents client targets (falls back to ``aws_region``)."""
        return self.documents_region or self.aws_region

    def bedrock_model_id(self, tier: str | None = None) -> str:
        """Bedrock model id for ``tier`` with the cross-region inference-profile
        geo prefix applied (e.g. ``eu.anthropic.claude-3-5-sonnet-…``)."""
        chosen = tier or self.bedrock_model_tier
        base = self.model_tiers[chosen].bedrock_id
        geo = _BEDROCK_GEO.get(self.bedrock_resolved_region.split("-", 1)[0], "")
        return f"{geo}.{base}" if geo else base

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
