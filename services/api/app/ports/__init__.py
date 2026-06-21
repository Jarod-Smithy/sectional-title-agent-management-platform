"""Ports — the interfaces the domain depends on (hexagonal architecture).

The domain layer imports only these Protocols, never a concrete backend. Local
dev wires in SQLite + the stub LLM; production wires in DynamoDB + Bedrock. No
domain code changes between the two.
"""

from __future__ import annotations

from app.ports.llm import LLM
from app.ports.repository import CorpusItem, Repository

__all__ = ["LLM", "CorpusItem", "Repository"]
