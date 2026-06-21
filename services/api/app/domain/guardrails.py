"""Governance Guardian — always-on gate over every outbound draft.

Ported from the prototype, decoupled from the DB: callers pass the list of
*signed* resolutions (the repository fetches them) instead of the guardian
reaching into sqlite. Three checks:

  1. Resolution gate — money/legal actions need a SIGNED resolution on file.
  2. No-go list      — five absolute prohibitions; always BLOCK.
  3. Defamation/tone — WARN on language that names individuals as at fault.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.schemas import GuardrailFinding, Resolution

_RESOLUTION_TRIGGERS: dict[str, list[str]] = {
    "levy": [
        r"\bspecial levy\b",
        r"\braise the levy\b",
        r"\bincrease the levy\b",
        r"\bimpose a levy\b",
        r"\blevy a special\b",
    ],
    "interest_penalty": [
        r"\bcharge\w* interest\b",
        r"\bapply\w* interest\b",
        r"\badd\w* interest\b",
        r"\binterest on (?:the )?arrears\b",
        r"\bimpose a penalty\b",
        r"\blevy a penalty\b",
        r"\blate fee\b",
    ],
    "legal_action": [
        r"\btake legal action\b",
        r"\blegal action against\b",
        r"\binstruct (?:our )?attorneys?\b",
        r"\bissue (?:a )?summons\b",
        r"\blitigat\w+\b",
        r"\bwe will sue\b",
    ],
    "recover_costs": [
        r"\brecover (?:the )?costs\b",
        r"\bclaim (?:the )?costs\b",
        r"\bdeduct\b.*\baccount\b",
    ],
    "fine": [
        r"\bimpose a fine\b",
        r"\bissue a fine\b",
        r"\bfine you\b",
        r"\blevy a fine\b",
    ],
}

_RESOLUTION_LOOKUP: dict[str, list[str]] = {
    "levy": ["special levy", "raise levy", "increase levy"],
    "interest_penalty": ["interest", "penalty"],
    "legal_action": ["legal action", "attorney", "litigation", "summons"],
    "recover_costs": ["recover costs", "claim costs"],
    "fine": ["fine"],
}

_NO_GOS = [
    (
        r"\bi (?:authorise|approve|release|pay|transfer)\b.*\b(?:r\s?\d|payment|funds?)\b",
        "Autonomous money movement is prohibited.",
    ),
    (
        r"\b(?:deduct|debit|charge)\b.*\baccount\b",
        "Directly charging an owner's account is prohibited.",
    ),
    (
        r"\bwe will (?:sue|take legal action|instruct (?:our )?attorneys?)\b",
        "Initiating legal action without trustee resolution is prohibited.",
    ),
    (
        r"\b(?:share|forward|disclose)\b.*\b(?:personal|owner|resident) "
        r"(?:details|information|data)\b",
        "Disclosing personal information to third parties is prohibited.",
    ),
    (
        r"\b(?:terminate|cut off|disconnect)\b.*\b(?:water|electricity|access)\b",
        "Disconnecting utilities/access is prohibited.",
    ),
]

_DEFAMATION = [
    r"\bnegligent\b",
    r"\bdishonest\b",
    r"\bfraud(?:ulent)?\b",
    r"\bliar\b",
    r"\bincompetent\b",
    r"\bstole\b",
    r"\bcorrupt\b",
]


def _signed_resolution_exists(
    keywords: list[str], unit: str, signed_resolutions: Iterable[Resolution]
) -> bool:
    """True only if a SIGNED resolution matches the keywords AND applies to this
    matter — scheme-wide ('') or explicitly referencing this unit."""
    want_unit = (unit or "").strip().lower()
    for res in signed_resolutions:
        res_unit = (res.unit or "").strip().lower()
        applies = res_unit == "" or res_unit == want_unit
        if applies and any(kw in res.keywords.lower() for kw in keywords):
            return True
    return False


def screen(
    text: str, unit: str, signed_resolutions: Iterable[Resolution]
) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    low = text.lower()
    resolutions = list(signed_resolutions)

    # 1. Resolution gate (matter-scoped to the unit the reply is about).
    for category, patterns in _RESOLUTION_TRIGGERS.items():
        if any(re.search(p, low) for p in patterns):
            if not _signed_resolution_exists(_RESOLUTION_LOOKUP[category], unit, resolutions):
                scope = f" for {unit}" if unit else ""
                findings.append(
                    GuardrailFinding(
                        rule=f"resolution-gate:{category}",
                        severity="block",
                        message=(
                            f"Proposes a {category.replace('_', ' ')} action{scope} "
                            "but no signed trustee resolution on file authorises it. "
                            "Cannot file until a resolution is recorded or the "
                            "wording is removed."
                        ),
                    )
                )

    # 2. No-go list.
    for pattern, message in _NO_GOS:
        if re.search(pattern, low):
            findings.append(GuardrailFinding(rule="no-go", severity="block", message=message))

    # 3. Defamation / tone.
    for pattern in _DEFAMATION:
        if re.search(pattern, low):
            findings.append(
                GuardrailFinding(
                    rule="defamation-screen",
                    severity="warn",
                    message=(
                        "Language may name an individual as at fault. Soften before "
                        "sending to avoid defamation risk."
                    ),
                )
            )
            break

    return findings


def has_block(findings: Iterable[GuardrailFinding]) -> bool:
    return any(f.severity == "block" for f in findings)
