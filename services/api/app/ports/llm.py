"""LLM port — the single seam to the language model.

Mirrors the prototype's ``llm.py`` Protocol. The stub implementation is offline
and deterministic; the Bedrock adapter (Increment 7) implements the same three
methods, so drafting / intake / RAG never change.
"""

from __future__ import annotations

from typing import Protocol


class LLM(Protocol):
    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str: ...

    def answer_question(self, *, question: str, context: list[str]) -> str: ...

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]: ...
