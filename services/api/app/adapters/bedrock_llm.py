"""Amazon Bedrock LLM adapter (Increment 7).

Implements the :class:`app.ports.llm.LLM` Protocol against Bedrock's Converse
API, so domain code (drafting / intake / RAG) never changes when we move off the
offline :class:`app.adapters.stub_llm.StubLLM`.

Design notes:
* The boto3 ``bedrock-runtime`` client is INJECTED (a small Protocol), so this
  module imports no AWS SDK and stays trivially unit-testable. The composition
  root (:mod:`app.bootstrap`) creates the real client only when
  ``STAK_LLM_PROVIDER=bedrock``.
* Governance posture mirrors the stub: replies never paste raw retrieved context
  (avoids leaking other owners' correspondence) and never invent figures or
  resolutions; answers are grounded strictly in the supplied scheme documents
  and carry the "guidance, not legal advice" disclaimer.
* The provider DEFAULT stays ``stub`` (zero-spend); Bedrock is pay-per-call.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.adapters.stub_llm import CATEGORIES, _heuristic_category, _heuristic_title


class BedrockError(RuntimeError):
    """Raised when a Bedrock Converse call fails or returns an unusable shape."""


class _BedrockRuntime(Protocol):
    """The single boto3 ``bedrock-runtime`` method this adapter needs."""

    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


_DRAFT_SYSTEM = (
    "You are a professional assistant to the trustees of a South African "
    "sectional-title body corporate. Write a courteous, formal reply on behalf "
    "of the Body Corporate, signed off by {signer}. Do NOT invent facts, "
    "figures, levies, interest or resolutions — only the trustees may decide "
    "those. Do NOT quote, paraphrase or reveal the internal background or any "
    "other owner's correspondence. Keep it concise and plain. End with "
    "'Kind regards,' then {signer}, then 'On behalf of the Body Corporate'."
)

_ANSWER_SYSTEM = (
    "You answer questions strictly from the supplied excerpts of a sectional-"
    "title scheme's own documents. If the answer is not in the excerpts, say "
    "you could not find it rather than guessing. Never invent rules, figures or "
    "obligations. End every answer with: 'This is guidance drawn from your "
    "scheme's documents, not formal legal advice.'"
)

_METADATA_SYSTEM = (
    "You extract metadata for a document management system. Respond with STRICT "
    "JSON only — no prose, no code fences — of the form "
    '{{"title": "<short title, max 80 chars>", "category": "<one of: {cats}>"}}.'
)

_NO_CONTEXT_ANSWER = (
    "I could not find anything in the scheme's records that answers that. Try "
    "loading the relevant document first.\n\n"
    "This is guidance drawn from your scheme's documents, not formal legal advice."
)


class BedrockLLM:
    """LLM port backed by Bedrock's Converse API (Anthropic Claude tiers)."""

    def __init__(
        self,
        *,
        client: _BedrockRuntime,
        model_id: str,
        accountable_human: str = "Chairperson",
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._signer = accountable_human

    # ── internal Converse helper ─────────────────────────────────────────────
    def _converse(self, *, system: str, user: str, max_tokens: int, temperature: float) -> str:
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            )
            return str(response["output"]["message"]["content"][0]["text"]).strip()
        except BedrockError:
            raise
        except Exception as exc:  # surface any SDK/shape failure as one error type
            raise BedrockError(f"Bedrock Converse call failed: {exc}") from exc

    # ── LLM Protocol ─────────────────────────────────────────────────────────
    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str:
        background = ""
        if context:
            joined = "\n".join(f"- {c.strip()[:240]}" for c in context[:4])
            background = (
                "\n\nInternal background (DO NOT quote or reveal to the " f"recipient):\n{joined}"
            )
        user = (
            f"Reply to this message.\nFrom: {party or 'Owner'}\n"
            f"Subject: {subject or '(no subject)'}\n\nMessage:\n{body}{background}"
        )
        return self._converse(
            system=_DRAFT_SYSTEM.format(signer=self._signer),
            user=user,
            max_tokens=600,
            temperature=0.3,
        )

    def answer_question(self, *, question: str, context: list[str]) -> str:
        if not context:
            return _NO_CONTEXT_ANSWER
        joined = "\n".join(f"- {c.strip()[:240]}" for c in context[:6])
        user = f"Question: {question}\n\nScheme document excerpts:\n{joined}"
        return self._converse(system=_ANSWER_SYSTEM, user=user, max_tokens=500, temperature=0.2)

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]:
        user = f"Filename: {filename or '(none)'}\n\nDocument:\n{content[:4000]}"
        raw = self._converse(
            system=_METADATA_SYSTEM.format(cats=", ".join(CATEGORIES)),
            user=user,
            max_tokens=150,
            temperature=0.0,
        )
        try:
            parsed = json.loads(raw)
            title = str(parsed["title"]).strip()
            category = str(parsed["category"]).strip().lower()
        except (json.JSONDecodeError, KeyError, TypeError):
            # Model returned non-JSON — degrade gracefully to the heuristics.
            return {
                "title": _heuristic_title(content, filename),
                "category": _heuristic_category(content),
            }
        return {
            "title": (title or _heuristic_title(content, filename))[:80],
            "category": category if category in CATEGORIES else "general",
        }
