"""LLM provider abstraction.

The product talks to this interface, never to a vendor SDK directly. Today it
resolves to an offline deterministic **stub** (zero setup) or **Anthropic
Claude** (if ANTHROPIC_API_KEY is set). The same seam becomes AWS Bedrock when
we deploy — drafting/intake/RAG code does not change.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Protocol

from . import config

# Fixed category vocabulary the document brain understands.
CATEGORIES = ("rules", "finance", "maintenance", "governance", "compliance", "general")
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": (
        "levy",
        "levies",
        "arrears",
        "interest",
        "budget",
        "payment",
        "statement",
        "account",
        "fee",
        "penalty",
        "invoice",
        "financial",
        "fund",
        "audit",
        "reserve",
    ),
    "maintenance": (
        "maintenance",
        "repair",
        "geyser",
        "plumbing",
        "garden",
        "pool",
        "gate",
        "building",
        "defect",
        "leak",
        "electrical",
        "contractor",
        "service",
        "paint",
    ),
    "rules": (
        "rule",
        "conduct",
        "noise",
        "pet",
        "parking",
        "nuisance",
        "behaviour",
        "behavior",
        "quiet",
        "tenant",
        "common property",
        "visitor",
    ),
    "governance": (
        "agm",
        "meeting",
        "trustee",
        "resolution",
        "quorum",
        "election",
        "vote",
        "notice",
        "governance",
        "chairperson",
        "minutes",
        "proxy",
        "round-robin",
    ),
    "compliance": (
        "compliance",
        "regulation",
        "insurance",
        "fire",
        "safety",
        "stsma",
        "ombud",
        "statutory",
        "clearance",
        "act ",
        "sectional titles",
        "prescribed",
    ),
}


def _heuristic_title(content: str, filename: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*$", stripped)
        candidate = (m.group(1) if m else stripped).strip()
        candidate = re.sub(r"^[-*•\d.\)\s]+", "", candidate).rstrip(":.").strip()
        candidate = re.sub(r"\s+", " ", candidate)
        if not candidate:
            continue
        if len(candidate) > 80:
            cut = candidate.rfind(" ", 0, 80)
            candidate = candidate[: cut if cut > 40 else 80].rstrip()
        return candidate
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename).replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "Untitled document"


def _heuristic_category(content: str) -> str:
    low = content.lower()
    best, best_score = "general", 0
    for category, words in _CATEGORY_KEYWORDS.items():
        score = sum(low.count(w) for w in words)
        if score > best_score:
            best, best_score = category, score
    return best


def _heuristic_metadata(content: str, filename: str) -> dict[str, str]:
    return {
        "title": _heuristic_title(content, filename),
        "category": _heuristic_category(content),
    }


def _guess_intent(subject: str, body: str) -> str:
    # Imported lazily to avoid a module import cycle at load time.
    from .intake import classify_intent

    return classify_intent(subject, body)


class LLM(Protocol):
    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str: ...

    def answer_question(self, *, question: str, context: list[str]) -> str: ...

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]: ...


# ── Offline stub ─────────────────────────────────────────────────────────────
class StubLLM:
    """Deterministic, offline. Good enough to feel the workflow with no key."""

    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str:
        greeting = f"Dear {party or 'Owner'},"
        intent = _guess_intent(subject, body)
        ack = (
            "Thank you for your message regarding "
            f'"{subject or "your enquiry"}". I confirm the trustees have '
            "received it and it has been logged for attention."
        )
        # Intent-specific, action-free body. We deliberately do NOT paste raw
        # retrieved context into the reply (that would risk leaking other
        # owners' correspondence and is not how a real model would write).
        # Grounding is surfaced to the trustee via the draft's "sources" list.
        middles = {
            "maintenance": (
                "Your maintenance report has been recorded. The trustees will "
                "arrange for the issue to be assessed and attended to in line "
                "with the scheme's maintenance plan, and we will keep you "
                "updated on progress."
            ),
            "complaint": (
                "We take conduct matters seriously. Your concern has been logged "
                "and will be considered by the trustees with reference to the "
                "scheme's conduct rules. We will revert once it has been reviewed."
            ),
            "financial": (
                "Your query about your account has been noted. A trustee will "
                "review it and respond with the relevant figures. Please note "
                "that any change to levies, interest or charges is only applied "
                "where the trustees have passed a formal resolution to that effect."
            ),
            "governance": (
                "Thank you for your input on this governance matter. It has been "
                "noted for the trustees' attention and, where appropriate, will "
                "be placed before the relevant meeting."
            ),
            "compliance": (
                "Your compliance-related query has been logged. The trustees will "
                "confirm the scheme's position and revert to you."
            ),
            "acknowledgement": (
                "We appreciate you taking the time to write in — your message is "
                "noted with thanks."
            ),
        }
        middle = middles.get(intent, "The trustees will review your message and revert shortly.")
        closing = (
            "\n\nPlease do not hesitate to contact us if anything is unclear."
            f"\n\nKind regards,\n{config.ACCOUNTABLE_HUMAN}\nOn behalf of the Body Corporate"
        )
        return f"{greeting}\n\n{ack}\n\n{middle}{closing}"

    def answer_question(self, *, question: str, context: list[str]) -> str:
        disclaimer = (
            "This is guidance drawn from your scheme's documents, not formal " "legal advice."
        )
        if not context:
            return (
                "I could not find anything in the scheme's records that answers "
                "that. Try loading the relevant document first.\n\n"
                f"{disclaimer}"
            )
        # Lead with a plain one-line summary, then show the grounding extracts so
        # the user sees *where* it came from rather than a raw chunk dump.
        joined = "\n".join(f"  • {c.strip()[:240]}" for c in context[:4])
        return "Here's what your documents say on this:\n\n" f"{joined}\n\n" f"{disclaimer}"

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]:
        # Deterministic, offline: first heading/line → title, keyword vote → category.
        return _heuristic_metadata(content, filename)


# ── Anthropic Claude ─────────────────────────────────────────────────────────
_DRAFT_SYSTEM = (
    "You are the assistant to the Chairperson of a South African sectional title "
    "body corporate. Draft a concise, warm, natural reply on behalf of the "
    "Chairperson. Never make legal threats, never name an individual as "
    "negligent, never authorise spending or money movement, never contact "
    "external parties. Ground statements in the supplied context; if unsure, say "
    "the trustees will revert. End with a sign-off from the Chairperson."
)
_ANSWER_SYSTEM = (
    "You answer trustee questions strictly from the supplied scheme records. "
    "Be concise and practical. If the context does not contain the answer, say "
    "so plainly rather than guessing."
)
_METADATA_SYSTEM = (
    "You file documents for a South African sectional title body corporate. "
    "Given a document's text, return a short descriptive title and the single "
    "best category. Respond with ONLY a JSON object: "
    '{"title": "...", "category": "..."}. The category must be exactly one of: '
    "rules, finance, maintenance, governance, compliance, general."
)


class AnthropicLLM:
    def __init__(self) -> None:
        self._key = config.ANTHROPIC_API_KEY
        self._model = config.ANTHROPIC_MODEL

    def _complete(self, system: str, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self._model,
                "max_tokens": 800,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()
        req = urllib.request.Request(  # noqa: S310 — fixed https endpoint
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "content-type": "application/json",
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = json.loads(resp.read())
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts).strip()
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return f"[LLM error: {exc}. Falling back to stub.]\n" + StubLLM().draft_reply(
                subject="", body=prompt, party="", context=[]
            )

    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str:
        ctx = "\n\n".join(context[:6]) or "(no grounding documents found)"
        prompt = (
            f"Inbound email from {party or 'an owner'}.\n"
            f"Subject: {subject}\n\nBody:\n{body}\n\n"
            f"Relevant scheme records:\n{ctx}\n\nDraft the reply."
        )
        return self._complete(_DRAFT_SYSTEM, prompt)

    def answer_question(self, *, question: str, context: list[str]) -> str:
        ctx = "\n\n".join(context[:6]) or "(no relevant records found)"
        prompt = f"Question: {question}\n\nScheme records:\n{ctx}"
        return self._complete(_ANSWER_SYSTEM, prompt)

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]:
        fallback = _heuristic_metadata(content, filename)
        prompt = (
            f"Filename: {filename or '(none)'}\n\n"
            f"Document content:\n{content[:6000]}\n\n"
            "Return the JSON object now."
        )
        raw = self._complete(_METADATA_SYSTEM, prompt)
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else {}
        except (ValueError, AttributeError):
            return fallback
        title = str(data.get("title", "")).strip()[:80]
        category = str(data.get("category", "")).strip().lower()
        if category not in CATEGORIES:
            category = fallback["category"]
        return {"title": title or fallback["title"], "category": category}


_PROVIDER: LLM | None = None


def get_llm() -> LLM:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = AnthropicLLM() if config.resolve_provider() == "anthropic" else StubLLM()
    return _PROVIDER


def provider_name() -> str:
    return config.resolve_provider()
