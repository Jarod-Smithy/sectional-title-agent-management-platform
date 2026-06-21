"""Offline, deterministic LLM — the zero-setup default (ported from the prototype).

Implements the :class:`app.ports.llm.LLM` Protocol. Good enough to feel the
whole workflow with no API key. The Bedrock adapter (Increment 7) implements the
same three methods, so domain code never changes.
"""

from __future__ import annotations

import re

from app.domain import intake

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


class StubLLM:
    """Deterministic, offline. Does NOT paste raw retrieved context into the
    reply (that would risk leaking other owners' correspondence)."""

    def __init__(self, accountable_human: str = "Chairperson") -> None:
        self._signer = accountable_human

    def draft_reply(self, *, subject: str, body: str, party: str, context: list[str]) -> str:
        greeting = f"Dear {party or 'Owner'},"
        intent = intake.classify_intent(subject, body)
        ack = (
            "Thank you for your message regarding "
            f'"{subject or "your enquiry"}". I confirm the trustees have '
            "received it and it has been logged for attention."
        )
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
            f"\n\nKind regards,\n{self._signer}\nOn behalf of the Body Corporate"
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
        joined = "\n".join(f"  • {c.strip()[:240]}" for c in context[:4])
        return "Here's what your documents say on this:\n\n" f"{joined}\n\n" f"{disclaimer}"

    def suggest_metadata(self, *, content: str, filename: str = "") -> dict[str, str]:
        return {
            "title": _heuristic_title(content, filename),
            "category": _heuristic_category(content),
        }
