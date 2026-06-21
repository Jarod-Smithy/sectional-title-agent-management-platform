"""Seed an anonymised sample scheme ("Acacia Heights Body Corporate").

Ported from the prototype. Loads documents, a signed resolution register, and a
set of inbound emails through the real intake pipeline so the dashboard has
content on first run. Includes a deliberate Governance-Guardian BLOCK demo.
"""

from __future__ import annotations

from app.domain import drafting, rag
from app.ports.llm import LLM
from app.ports.repository import Repository
from app.schemas import EmailIn

_DOCUMENTS: list[tuple[str, str, str, str]] = [
    (
        "Conduct Rules — Acacia Heights",
        "rules",
        "2023-03-01",
        """Conduct Rules of Acacia Heights Body Corporate (SS 124/2008).

Noise: No owner or resident shall create a nuisance. Quiet hours are 22:00 to
06:00 daily. Repeated breaches may be referred to the trustees.

Pets: One small pet per unit is permitted with prior written trustee consent.
Dogs must be leashed in all common areas. Owners are responsible for waste.

Parking: Each unit is allocated one bay. Visitor bays are for visitors only and
may not be used for storage or long-term parking.

Common property: Owners may not alter, paint, or attach anything to common
property without trustee approval.""",
    ),
    (
        "Levy & Finance Policy — Acacia Heights",
        "finance",
        "2024-01-15",
        """Levy and Finance Policy.

Levies are payable monthly in advance, on or before the 1st of each month.

Arrears: Accounts in arrears for more than 30 days will receive a reminder.
Interest on arrears, special levies, and any recovery costs may ONLY be applied
where a formal trustee resolution authorises it. No interest or penalty is
charged automatically without such a resolution.

Statements: Owners may request a statement of account at any time and one will
be provided within five working days.""",
    ),
    (
        "Maintenance Plan — Acacia Heights",
        "maintenance",
        "2024-06-01",
        """10-Year Maintenance Plan summary.

Routine: Garden service weekly. Pool service twice weekly in summer. Gate motor
serviced quarterly. Fire equipment inspected annually.

Reactive repairs: Owners must report defects on common property to the trustees
in writing. The managing agent obtains quotes; trustees approve spend per the
finance policy. Emergencies (burst pipes, electrical danger, security failures)
are attended to immediately and reported to trustees after the fact.

Geysers: Geysers inside a section are the owner's responsibility. Common-property
plumbing is the body corporate's responsibility.""",
    ),
    (
        "Governance & Meetings — Acacia Heights",
        "governance",
        "2023-11-20",
        """Governance notes.

The AGM is held annually within four months of financial year-end. Notice of at
least 14 days is given to all owners. A quorum is one third of the value of votes.

Trustees are elected at the AGM and hold office until the next AGM. Trustee
decisions between meetings are made by round-robin resolution and recorded in
the resolution register.

Special general meetings may be called by the trustees or on written request of
owners holding at least 25% of votes.""",
    ),
]

_RESOLUTIONS: list[tuple[str, str, bool, str, str, str]] = [
    (
        "Annual garden & pool maintenance contract",
        "2024-06-05",
        True,
        "Trustees approved the annual grounds maintenance contract with GreenCare.",
        "maintenance garden pool contract spend",
        "",
    ),
    (
        "Arrears interest — Unit 14 only",
        "2024-09-10",
        True,
        "Trustees resolved to apply interest on the arrears account of Unit 14 "
        "following non-payment over 90 days, per the finance policy.",
        "interest penalty arrears unit 14 recover costs",
        "Unit 14",
    ),
]

_EMAILS: list[tuple[str, str, str, str]] = [
    (
        "j.naidoo@gmail.com",
        "Leaking geyser flooding Unit 12",
        "Hi trustees, there is water coming through my ceiling from the unit "
        "above. It looks like a burst geyser. This is urgent, please help asap.",
        "Unit 12",
    ),
    (
        "sara.botha@gmail.com",
        "Noise complaint — Unit 7 parties",
        "Good evening. Unit 7 has had loud music past midnight three nights this "
        "week. It is disturbing my children. What can be done?",
        "Unit 9",
    ),
    (
        "m.vandermerwe@gmail.com",
        "Levy statement request",
        "Hello, could you please send me a statement of my levy account for the "
        "past six months? Thank you.",
        "Unit 3",
    ),
    (
        "trustee.chair@gmail.com",
        "Thanks for the quick fix",
        "Thank you for sorting out the gate motor so quickly, much appreciated.",
        "Unit 1",
    ),
    (
        "k.dlamini@gmail.com",
        "Arrears on Unit 3 — what happens next",
        "Hi, my levy account for Unit 3 is behind. I want to understand what the "
        "trustees intend to do about the arrears. Please advise.",
        "Unit 3",
    ),
]

_BLOCK_DEMO_SUBJECT = "Arrears on Unit 3 — what happens next"
_BLOCK_DEMO_BODY = (
    "Dear Owner,\n\n"
    "Thank you for your email regarding the arrears on Unit 3.\n\n"
    "The trustees will charge interest on the outstanding arrears and will take "
    "legal action to recover the costs if payment is not received within seven "
    "days.\n\n"
    "Regards,\nThe Trustees\nAcacia Heights Body Corporate"
)


def seed(repo: Repository, llm: LLM) -> dict[str, int]:
    repo.reset()

    for title, category, eff, content in _DOCUMENTS:
        chunks = rag.chunk_document(title, content)
        repo.add_document(
            title=title,
            content=content,
            category=category,
            effective_date=eff,
            chunks=chunks,
        )
    for title, eff, signed, summary, keywords, unit in _RESOLUTIONS:
        repo.add_resolution(
            title=title,
            effective_date=eff,
            signed=signed,
            summary=summary,
            keywords=keywords,
            unit=unit,
        )

    for sender, subject, body, from_unit in _EMAILS:
        draft = drafting.process_inbound(
            repo, llm, EmailIn(sender=sender, subject=subject, body=body, from_unit=from_unit)
        )
        if subject == _BLOCK_DEMO_SUBJECT:
            drafting.edit_draft(repo, draft.id, _BLOCK_DEMO_BODY)

    return {
        "documents": repo.count_documents(),
        "drafts": len(repo.list_drafts()),
        "resolutions": len(repo.list_resolutions()),
        "tickets": len(repo.list_tickets()),
    }
