"""Configuration and filesystem paths for the prototype."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROTOTYPE_DIR = APP_DIR.parent
DATA_DIR = PROTOTYPE_DIR / "data"
WEB_DIR = PROTOTYPE_DIR / "web"

DB_PATH = DATA_DIR / "app.db"

# Accountable human for every AI action (Vision §3).
ACCOUNTABLE_HUMAN = "Chairperson"

# Trusted chairman address(es). An inbound email from one of these *with* a
# "TASK:"/"TODO:" subject prefix is treated as a task instruction (it creates a
# board task directly instead of a reply draft). Override via env, comma-list.
CHAIRMAN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get(
        "STAP_CHAIRMAN_EMAILS", "trustee.chair@gmail.com, chair@acaciaheights.co.za"
    ).split(",")
    if e.strip()
}

# LLM selection: "stub" (default, offline) or "anthropic".
LLM_PROVIDER = os.environ.get("STAP_LLM", "").strip().lower()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("STAP_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")


def resolve_provider() -> str:
    """Pick the LLM provider: explicit env wins, else auto-detect a key."""
    if LLM_PROVIDER in {"stub", "anthropic"}:
        return LLM_PROVIDER
    return "anthropic" if ANTHROPIC_API_KEY else "stub"


# ── Specialist agent assist (maps to AWS AgentCore in production) ─────────────
# The "Get agent help" feature is gated three ways: a global enable flag, a
# hard kill-switch, and an explicit per-task click — because AgentCore runs are
# asynchronous and cost money. RUNTIME holds the live toggle state (a prototype
# stand-in for a control-plane flag / SSM parameter).
RUNTIME: dict[str, bool] = {
    "assist_enabled": os.environ.get("STAP_ASSIST_ENABLED", "1").strip() != "0",
    "kill_switch": False,
}


def assist_available() -> bool:
    """Agent assist may run only when enabled AND the kill-switch is off."""
    return RUNTIME["assist_enabled"] and not RUNTIME["kill_switch"]


# Complexity → reasoning-model tier. The orchestrator sizes the task and picks
# the cheapest model that can do the job (cost discipline). Bedrock IDs are the
# production targets; the prototype only records which tier it would have used.
MODEL_TIERS: dict[str, dict[str, object]] = {
    "fast": {
        "label": "Claude Haiku",
        "bedrock_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "cost_per_run": 0.01,
    },
    "balanced": {
        "label": "Claude Sonnet",
        "bedrock_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "cost_per_run": 0.06,
    },
    "deep": {
        "label": "Claude Opus",
        "bedrock_id": "anthropic.claude-opus-4-20250514-v1:0",
        "cost_per_run": 0.30,
    },
}

# Capability manifest — the declared allow-list of what specialist agents may
# do. The agent consults this before acting; anything outside it is NOT done
# silently — instead the agent proposes a new permanent MCP tool via a PR.
CAPABILITIES: dict[str, list[str]] = {
    "read": [
        "document_brain",  # RAG over scheme documents
        "resolution_register",  # signed resolutions (source of truth)
        "interaction_ledger",  # correspondence history across threads
        "ticket",  # the task itself
    ],
    "draft": [
        "resolution_template",
        "correspondence",  # human-sent only
        "action_plan",
        "research_brief",
        "owner_circular",
    ],
    "compute": [
        "levy_interest",  # code-interpreter: interest on arrears (needs signed rate)
        "reserve_projection",  # code-interpreter: 10-yr reserve modelling
        "budget_model",  # code-interpreter: annual budget draft
        "quote_comparison",  # code-interpreter: compare collected quotes
    ],
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
