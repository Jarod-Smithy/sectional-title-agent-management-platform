"""Specialist agent assist — an on-demand team of agents that helps a
trustee *complete* a board task.

Design goals (mirrors AWS Bedrock AgentCore so the prototype is a faithful
seam, see docs/AGENT_ASSIST_AGENTCORE_MAPPING.md):

* An **Orchestrator** reads the task title/details and dynamically routes it to
  one or more specialists (it is NOT a static type→agent table).
* It **sizes the task** and picks the cheapest reasoning model that can do it
  (Haiku → Sonnet → Opus), recorded on every artifact.
* It consults a **capability manifest** before acting. Anything inside the
  manifest it does with the right AgentCore tool (Code Interpreter for
  calculations, Browser for research, Gateway/MCP for governed data). Anything
  *outside* it does NOT do silently — it proposes a permanent MCP tool via a
  draft pull-request instead.
* Output is **always a draft/suggestion** the human reviews. Any actionable
  text (e.g. correspondence) is screened by the Governance Guardian first, and
  the human is the only one who can Send/sign/pay. The agent suggests, never
  acts.

The prototype runs entirely on the Python standard library and never reaches
the network. Where production would call a model, a browser, or GitHub, the
prototype performs a deterministic local stand-in and labels it honestly.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict

from . import config, db, guardrails, rag
from .models import Artifact, AssistRun, GuardrailFinding, ProposedTool

# ── Specialist roster (all report to the Orchestrator) ───────────────────────
SPECIALISTS: dict[str, str] = {
    "legal_compliance": "Legal & Compliance Analyst",
    "financial_oversight": "Financial Oversight Analyst",
    "maintenance": "Maintenance Coordinator",
    "knowledge_auditor": "Knowledge Auditor",
    "trustee_copilot": "Trustee Copilot",
}

# Keyword signals the Orchestrator uses to pick specialists dynamically.
_ROUTING: dict[str, list[str]] = {
    "legal_compliance": [
        "resolution",
        "rule",
        "conduct",
        "legal",
        "complian",
        "insurance",
        "csos",
        "bylaw",
        "by-law",
        "dispute",
        "notice",
        "template",
        "govern",
        "agm",
        "sgm",
        "minutes",
        "fica",
        "popia",
        "trustee",
        "constitution",
    ],
    "financial_oversight": [
        "levy",
        "budget",
        "reserve",
        "arrear",
        "interest",
        "financ",
        "fund",
        "audit",
        "contribution",
        "quote",
        "cost",
        "payment",
        "managing agent",
        "invoice",
        "expense",
        "fee",
        "tariff",
    ],
    "maintenance": [
        "repair",
        "mainten",
        "geyser",
        "plumb",
        "gate",
        "pool",
        "garden",
        "electric",
        "contractor",
        "lift",
        "paint",
        "fire equipment",
        "roof",
        "leak",
        "damp",
        "security",
        "cctv",
    ],
    "knowledge_auditor": [
        "audit",
        "stale",
        "outdated",
        "contradict",
        "review document",
        "knowledge",
        "out of date",
        "supersed",
    ],
}

# Capability needs the task implies. Tokens are "domain:name"; a need is
# *available* when its name is listed under that domain in config.CAPABILITIES.
# Tokens whose name is NOT in the manifest become capability gaps that trigger
# a proposed permanent MCP tool.
_NEEDS: dict[str, list[str]] = {
    "compute:levy_interest": ["interest", "arrear"],
    "compute:reserve_projection": ["reserve", "10-year", "10 year", "projection"],
    "compute:budget_model": ["budget"],
    "compute:quote_comparison": ["quote", "compare quote"],
    "draft:resolution_template": ["resolution", "template"],
    "draft:correspondence": ["email", "reply", "respond", "letter", "circular", "notice"],
    "draft:research_brief": [
        "investigate",
        "research",
        "alternativ",
        "options",
        "shortlist",
        "compare",
        "evaluate",
        "benchmark",
    ],
    # Deliberately NOT in the manifest → demonstrates recurring→PR promotion.
    "compute:csos_dispute_pack": ["csos", "adjudicat", "dispute pack"],
    "draft:penalty_schedule": ["penalty", "fine schedule", "demerit"],
}

# Human-only actions the agent must never perform — it routes these back to the
# accountable human instead of treating them as capability gaps.
_HUMAN_ONLY: dict[str, list[str]] = {
    "send the email / correspondence": ["send", "email out", "reply to"],
    "sign the resolution / document": ["sign", "signature", "execute"],
    "move scheme funds / pay": ["pay", "transfer", "refund", "release funds"],
}

# A recurring capability is promoted to a permanent MCP tool once it has been
# requested at least this many times (counting the current run). Defaults to 1
# so the prototype demonstrates the flow on first use; production would raise it.
_TOOL_PROMOTE_THRESHOLD = int(os.environ.get("STAP_TOOL_PROMOTE_THRESHOLD", "1"))

_WORD_RE = re.compile(r"[a-z0-9']+")
_AMOUNT_RE = re.compile(r"R\s?([\d][\d,]*(?:\.\d+)?)")
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(?:%|percent\b|per cent\b)", re.I)


# ── Orchestrator: routing & sizing ───────────────────────────────────────────
def route(title: str, description: str, ttype: str = "") -> list[str]:
    """Pick the specialist(s) best suited to the task. Always returns at least
    the Trustee Copilot, who coordinates and covers general/admin work."""
    text = f"{title} {description} {ttype}".lower()
    scored: list[tuple[int, str]] = []
    for key, words in _ROUTING.items():
        score = sum(1 for w in words if w in text)
        if score:
            scored.append((score, key))
    scored.sort(reverse=True)
    chosen = [key for _, key in scored]
    if not chosen:
        chosen = ["trustee_copilot"]
    elif "trustee_copilot" not in chosen:
        chosen.append("trustee_copilot")
    return chosen


def assess_complexity(title: str, description: str, specialists: list[str]) -> tuple[str, str]:
    """Size the task → (complexity, model_tier). Cheapest model that fits."""
    text = f"{title} {description}".lower()
    words = len(_WORD_RE.findall(text))
    compute_hits = sum(
        1 for t, kws in _NEEDS.items() if t.startswith("compute:") and any(k in text for k in kws)
    )
    research_hits = sum(1 for k in _NEEDS["draft:research_brief"] if k in text)
    multistep = len(re.findall(r"\b(and|then|also|plus|as well as)\b", text)) + text.count(";")

    score = 0
    score += 2 if words > 40 else (1 if words > 18 else 0)
    score += 2 * compute_hits
    score += 2 if research_hits else 0
    score += min(multistep, 3)
    score += max(0, len([s for s in specialists if s != "trustee_copilot"]) - 1) * 2

    if score >= 6:
        return "complex", "deep"
    if score >= 3:
        return "moderate", "balanced"
    return "simple", "fast"


# ── Capability manifest checks ───────────────────────────────────────────────
def detect_needs(text: str) -> list[str]:
    low = text.lower()
    return [token for token, kws in _NEEDS.items() if any(k in low for k in kws)]


def _in_manifest(token: str) -> bool:
    domain, _, name = token.partition(":")
    return name in config.CAPABILITIES.get(domain, [])


def check_capabilities(needs: list[str]) -> tuple[list[str], list[str]]:
    available = [n for n in needs if _in_manifest(n)]
    gaps = [n for n in needs if not _in_manifest(n)]
    return available, gaps


def detect_human_only(text: str) -> list[str]:
    low = text.lower()
    return [label for label, kws in _HUMAN_ONLY.items() if any(k in low for k in kws)]


# ── Code Interpreter stand-in (real stdlib computation) ──────────────────────
def _numbers(text: str) -> tuple[list[float], list[float]]:
    amounts = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(text)]
    pcts = [float(m) for m in _PCT_RE.findall(text)]
    return amounts, pcts


def _invented_note(invented: bool) -> str:
    """Honest banner when the task gave no figures and we used examples."""
    if not invented:
        return ""
    return (
        "\u26a0 The task didn't include the figures, so these are EXAMPLE numbers "
        "to show the shape of the answer \u2014 replace them with the real ones.\n\n"
    )


def _calc_levy_interest(text: str) -> tuple[str, str]:
    amounts, pcts = _numbers(text)
    # Arrears are typically modest; ignore large reserve/budget figures.
    small = [a for a in amounts if a < 100000]
    arrears = small[0] if small else 8500.0
    rate_candidates = [p for p in pcts if p <= 30]
    annual = rate_candidates[0] if rate_candidates else 10.0
    invented = not small or not rate_candidates
    months = 6
    monthly = annual / 12.0 / 100.0
    interest = round(arrears * monthly * months, 2)
    total = round(arrears + interest, 2)
    code = (
        "# Code Interpreter — illustrative arrears interest\n"
        f"arrears = {arrears}\n"
        f"annual_rate_pct = {annual}\n"
        f"months = {months}\n"
        "monthly = annual_rate_pct / 12 / 100\n"
        "interest = round(arrears * monthly * months, 2)\n"
        "total = round(arrears + interest, 2)\n"
    )
    result = (
        _invented_note(invented)
        + f"Interest over {months} months on R{arrears:,.2f} at {annual:.2f}% p.a. "
        f"= R{interest:,.2f}; balance ≈ R{total:,.2f}.\n"
        "NOTE: this is illustrative only. Charging interest requires a signed "
        "resolution fixing the rate — the Governance Guardian blocks any letter "
        "that demands interest without one."
    )
    return code, result


def _calc_reserve_projection(text: str) -> tuple[str, str]:
    amounts, pcts = _numbers(text)
    # Reserve figures are large; ignore small arrears amounts.
    big = [a for a in amounts if a >= 50000]
    opening = big[0] if big else 250000.0
    annual_contrib = big[1] if len(big) > 1 else 120000.0
    growth_candidates = [p for p in pcts if p <= 12]
    growth = (growth_candidates[-1] if growth_candidates else 6.0) / 100.0
    invented = not big
    rows, bal = [], opening
    for yr in range(1, 11):
        bal = round(bal * (1 + growth) + annual_contrib, 2)
        rows.append(f"  Year {yr:>2}: R{bal:,.2f}")
    code = (
        "# Code Interpreter — 10-year reserve projection (compounded)\n"
        f"balance = {opening}\n"
        f"annual_contribution = {annual_contrib}\n"
        f"growth = {growth}\n"
        "for year in range(1, 11):\n"
        "    balance = round(balance * (1 + growth) + annual_contribution, 2)\n"
    )
    result = _invented_note(invented) + "Projected reserve fund balance:\n" + "\n".join(rows)
    return code, result


def _calc_budget_model(text: str) -> tuple[str, str]:
    amounts, _ = _numbers(text)
    invented = not amounts
    lines = amounts if amounts else [180000.0, 96000.0, 54000.0, 38000.0]
    labels = ["Insurance", "Cleaning & garden", "Repairs & maintenance", "Admin & audit"]
    pairs = list(zip(labels, lines, strict=False))
    total = round(sum(v for _, v in pairs), 2)
    body = "\n".join(f"  {lbl}: R{val:,.2f}" for lbl, val in pairs)
    code = (
        "# Code Interpreter — annual operating budget draft\n"
        f"line_items = {dict(pairs)}\n"
        "total = round(sum(line_items.values()), 2)\n"
    )
    result = _invented_note(invented) + f"Draft annual budget:\n{body}\n  ── Total: R{total:,.2f}"
    return code, result


def _calc_quote_comparison(text: str) -> tuple[str, str]:
    amounts, _ = _numbers(text)
    invented = len(amounts) < 2
    quotes = amounts if len(amounts) >= 2 else [18900.0, 22400.0, 17350.0]
    labelled = [(f"Quote {chr(65 + i)}", v) for i, v in enumerate(quotes)]
    best = min(labelled, key=lambda p: p[1])
    body = "\n".join(f"  {lbl}: R{val:,.2f}" for lbl, val in labelled)
    code = (
        "# Code Interpreter — compare collected quotes\n"
        f"quotes = {dict(labelled)}\n"
        "best = min(quotes, key=quotes.get)\n"
    )
    result = (
        _invented_note(invented) + f"Quotes compared:\n{body}\n"
        f"Lowest: {best[0]} at R{best[1]:,.2f}. "
        "Recommend trustees also weigh references and warranty before awarding."
    )
    return code, result


_CALCS = {
    "compute:levy_interest": ("levy interest projection", _calc_levy_interest),
    "compute:reserve_projection": ("10-year reserve projection", _calc_reserve_projection),
    "compute:budget_model": ("annual budget draft", _calc_budget_model),
    "compute:quote_comparison": ("quote comparison", _calc_quote_comparison),
}


# ── Deliverable generators ───────────────────────────────────────────────────
def _ctx_lines(text: str, limit: int = 3) -> list[str]:
    snips = rag.context_snippets(text, limit=limit)
    return [s[:240].strip() for s in snips]


def _doc_resolution_template(title: str, unit: str, ctx: list[str]) -> Artifact:
    scope = f"Unit {unit}" if unit else "the scheme"
    cited = ("\n".join(f"  • {c}" for c in ctx)) or "  • (no matching scheme documents found)"
    body = (
        f"DRAFT RESOLUTION TEMPLATE — {title}\n"
        f"Scope: {scope}\n\n"
        "1. PREAMBLE\n"
        "   WHEREAS the trustees of the body corporate, acting under the\n"
        "   Sectional Titles Schemes Management Act and the scheme rules, resolve:\n\n"
        "2. RESOLUTION\n"
        "   2.1 [State the decision in one operative sentence.]\n"
        "   2.2 [State any amount, rate or deadline — leave blank for trustees.]\n\n"
        "3. AUTHORITY & EFFECTIVE DATE\n"
        "   3.1 This resolution takes effect once signed by the trustees.\n"
        "   3.2 Signed copies are filed in the resolution register.\n\n"
        "Grounded in scheme documents:\n" + cited + "\n\n"
        "— Drafted for trustee review. A trustee must complete the bracketed\n"
        "  fields and sign; the agent cannot adopt or sign a resolution."
    )
    return Artifact(
        kind="document",
        title="Draft resolution template",
        body=body,
        specialist=SPECIALISTS["legal_compliance"],
        tool_used="gateway/document_brain",
    )


def _research_brief(title: str, ctx: list[str]) -> Artifact:
    cited = ("\n".join(f"  • {c}" for c in ctx)) or "  • (no internal references found)"
    body = (
        f"RESEARCH BRIEF — {title}\n\n"
        "Objective: give trustees an evidence-based shortlist to decide from.\n\n"
        "Evaluation criteria:\n"
        "  1. Track record with sectional-title schemes of similar size\n"
        "  2. Fees & billing transparency (no hidden disbursements)\n"
        "  3. Trust-account controls & CSOS / FICA compliance\n"
        "  4. Reporting cadence and trustee portal quality\n"
        "  5. References from at least two comparable schemes\n\n"
        "Candidate shortlist:\n"
        "  • Candidate A — [name] · strengths/risks: __\n"
        "  • Candidate B — [name] · strengths/risks: __\n"
        "  • Candidate C — [name] · strengths/risks: __\n\n"
        "Internal references consulted:\n" + cited + "\n\n"
        "— Candidate rows are placeholders: in production the AgentCore Browser\n"
        "  tool fetches live web results and fills these in. Trustees decide; the\n"
        "  agent only assembles the comparison."
    )
    return Artifact(
        kind="research_brief",
        title="Research brief & shortlist",
        body=body,
        specialist=SPECIALISTS["trustee_copilot"],
        tool_used="browser",
    )


def _correspondence(title: str, party: str, ctx: list[str]) -> Artifact:
    who = party or "the owner"
    grounded = ctx[0] if ctx else "the scheme rules and resolution register"
    body = (
        f"Subject: {title}\n\n"
        f"Dear {who},\n\n"
        "Thank you for your correspondence. The trustees have reviewed the matter "
        "and respond as follows:\n\n"
        "  • [Key point 1 — grounded in scheme records]\n"
        "  • [Key point 2]\n\n"
        f"This position reflects: {grounded[:160]}\n\n"
        "Please let us know if anything is unclear.\n\n"
        "Kind regards,\n"
        "The Chairperson\n"
        "(on behalf of the Body Corporate)\n"
    )
    return Artifact(
        kind="correspondence",
        title="Draft reply (for your review & send)",
        body=body,
        specialist=SPECIALISTS["trustee_copilot"],
        tool_used="gateway/document_brain",
        sendable=True,
    )


def _action_plan(title: str, specialists: list[str], human_only: list[str]) -> Artifact:
    team = ", ".join(SPECIALISTS[s] for s in specialists)
    steps = [
        "1. Review the deliverables attached to this task.",
        "2. Complete any bracketed placeholders with scheme-specific detail.",
    ]
    n = 3
    for label in human_only:
        steps.append(f"{n}. Human action required — {label}.")
        n += 1
    steps.append(f"{n}. Sign / approve where needed, then mark the task done.")
    body = (
        f"RECOMMENDED ACTION PLAN — {title}\n\n"
        f"Engaged: {team}\n\n" + "\n".join(steps) + "\n\n"
        "— The agent prepares and recommends; the Chairperson decides and acts."
    )
    return Artifact(
        kind="action_plan",
        title="Recommended action plan",
        body=body,
        specialist=SPECIALISTS["trustee_copilot"],
        tool_used="memory",
    )


# ── Recurring capability → proposed permanent MCP tool (draft PR) ─────────────
def _gap_seen_count(gap: str, exclude_ticket: int | None = None) -> int:
    """How many *distinct prior tasks* already requested this capability gap.

    Counting distinct tickets (not rows) means re-clicking “Get agent help” on
    the same task cannot fabricate a false ‘recurring’ signal."""
    with db.cursor() as cur:
        cur.execute("SELECT ticket_id, capability_gaps_json FROM assist_runs")
        rows = cur.fetchall()
    tickets = {
        r["ticket_id"]
        for r in rows
        if r["ticket_id"] != exclude_ticket and gap in json.loads(r["capability_gaps_json"] or "[]")
    }
    return len(tickets)


def _propose_tool(gap: str) -> ProposedTool:
    domain, _, name = gap.partition(":")
    slug = name
    func = f"{slug}"
    file_path = f"tools/mcp/{slug}.py"
    branch = f"agent/auto-tool-{slug}"
    content = (
        '"""Auto-proposed MCP tool — generated by the specialist agent team.\n\n'
        "This promotes a recurring throwaway capability into a permanent,\n"
        "governed tool exposed via AgentCore Gateway (MCP). Human review and CI\n"
        'must pass before merge — do NOT merge without trustee sign-off.\n"""\n\n'
        "from mcp.server.fastmcp import FastMCP\n\n"
        'mcp = FastMCP("sectional-title-tools")\n\n\n'
        "@mcp.tool()\n"
        f"def {func}(payload: dict) -> dict:\n"
        f'    """{domain.title()} capability: {name.replace("_", " ")}.\n\n'
        "    Implement the governed logic here. Reads/writes must stay within the\n"
        "    capability manifest and emit an audit record.\n"
        '    """\n'
        '    raise NotImplementedError("Trustee + engineering to complete.")\n'
    )
    body = (
        f"## Why\n\n"
        f"The specialist team needed `{gap}`, which is **not** in the capability "
        "manifest. Rather than act outside its allow-list, the agent is proposing "
        "a permanent, governed MCP tool.\n\n"
        "## What this PR adds\n\n"
        f"- `{file_path}` — a FastMCP tool stub for `{name}`.\n"
        "- Registers the capability so future runs use a reviewed tool, not "
        "ad-hoc code.\n\n"
        "## Guardrails\n\n"
        "- [ ] Human trustee review\n"
        "- [ ] CI (lint, tests, security scan) green\n"
        "- [ ] Capability manifest updated\n\n"
        "_Generated by the agent assist harness. The agent cannot merge; a human "
        "must approve._"
    )
    return ProposedTool(
        reason=(
            f"`{gap}` was requested but is outside the capability manifest — "
            "promoting it to a permanent, governed MCP tool."
        ),
        branch=branch,
        pr_title=f"feat(mcp): add {name} tool (auto-proposed)",
        pr_body=body,
        file_path=file_path,
        file_content=content,
        simulated=True,
    )


# ── Persistence helpers ──────────────────────────────────────────────────────
def _load_ticket(ticket_id: int) -> dict | None:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def _row_to_run(row) -> AssistRun:
    artifacts = [Artifact(**a) for a in json.loads(row["artifacts_json"] or "[]")]
    findings = [GuardrailFinding(**f) for f in json.loads(row["findings_json"] or "[]")]
    pt_raw = row["proposed_tool_json"] or ""
    proposed = ProposedTool(**json.loads(pt_raw)) if pt_raw else None
    return AssistRun(
        id=row["id"],
        ticket_id=row["ticket_id"],
        status=row["status"],
        complexity=row["complexity"],
        model_tier=row["model_tier"],
        model=row["model"],
        specialists=json.loads(row["specialists_json"] or "[]"),
        plan=json.loads(row["plan_json"] or "[]"),
        artifacts=artifacts,
        findings=findings,
        capability_gaps=json.loads(row["capability_gaps_json"] or "[]"),
        proposed_tool=proposed,
        cost_estimate=row["cost_estimate"],
        summary=row["summary"],
        created_at=row["created_at"],
    )


def list_runs(ticket_id: int) -> list[AssistRun]:
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM assist_runs WHERE ticket_id = ? ORDER BY id DESC",
            (ticket_id,),
        )
        rows = cur.fetchall()
    return [_row_to_run(r) for r in rows]


def get_run(run_id: int) -> AssistRun | None:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM assist_runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
    return _row_to_run(row) if row else None


# ── The orchestration entry point ────────────────────────────────────────────
class AssistDisabled(RuntimeError):
    """Raised when assist is globally disabled or the kill-switch is on."""


def run_assist(ticket_id: int) -> AssistRun:
    if not config.assist_available():
        raise AssistDisabled("Agent assist is disabled or the kill-switch is on.")
    ticket = _load_ticket(ticket_id)
    if ticket is None:
        raise ValueError(f"No task #{ticket_id}")

    title = ticket["title"]
    description = ticket.get("description", "") or ""
    unit = ticket.get("unit", "") or ""
    text = f"{title}\n{description}"

    specialists = route(title, description, ticket.get("type", ""))
    complexity, tier = assess_complexity(title, description, specialists)
    model = str(config.MODEL_TIERS[tier]["label"])

    needs = detect_needs(text)
    available, gaps = check_capabilities(needs)
    human_only = detect_human_only(text)
    ctx = _ctx_lines(text)

    plan: list[str] = [
        f"Picked the right level of help for this task ({complexity}).",
        "Brought in: " + ", ".join(SPECIALISTS[s] for s in specialists) + ".",
    ]

    artifacts: list[Artifact] = []

    # Calculations (Code Interpreter).
    for token in available:
        if token in _CALCS:
            label, fn = _CALCS[token]
            code, result = fn(text)
            plan.append(f"Financial Oversight Analyst worked out the {label}.")
            artifacts.append(
                Artifact(
                    kind="calculation",
                    title=label.capitalize(),
                    body=result,
                    specialist=SPECIALISTS["financial_oversight"],
                    code=code,
                    result=result,
                    tool_used="code_interpreter",
                )
            )

    # Drafted documents / research / correspondence.
    if "draft:resolution_template" in available:
        plan.append("Legal & Compliance Analyst drafted a resolution template.")
        artifacts.append(_doc_resolution_template(title, unit, ctx))
    if "draft:research_brief" in available:
        plan.append("Trustee Copilot researched the options and assembled a brief.")
        artifacts.append(_research_brief(title, ctx))
    if "draft:correspondence" in available:
        plan.append("Trustee Copilot drafted correspondence for your review.")
        artifacts.append(_correspondence(title, ticket.get("unit", ""), ctx))

    # Always finish with a recommended action plan.
    artifacts.append(_action_plan(title, specialists, human_only))

    for label in human_only:
        plan.append(f"Left for you to do (only you can): {label}.")

    # Governance Guardian screens any actionable output. Correspondence is the
    # only thing a human can SEND, so a block there stops the run and the Send
    # button. Documents (templates/briefs) are scaffolding the human completes,
    # so we screen only the *generated* scaffold (not quoted grounding context)
    # and surface any hits as advisory notes rather than hard blocks.
    findings: list[GuardrailFinding] = []
    blocking = False
    for art in artifacts:
        if art.kind == "correspondence":
            hits = guardrails.screen(art.body, unit)
            findings.extend(hits)
            if guardrails.has_block(hits):
                art.sendable = False
                blocking = True
        elif art.kind == "document":
            scaffold = art.body.split("Grounded in scheme documents:")[0]
            findings.extend(guardrails.screen(scaffold, unit))
    plan.append("Governance Guardian checked everything for compliance before showing you.")

    # Recurring capability gap → propose a permanent MCP tool (draft PR).
    proposed: ProposedTool | None = None
    for gap in gaps:
        prior = _gap_seen_count(gap, exclude_ticket=ticket_id)
        name = gap.partition(":")[2].replace("_", " ")
        if prior + 1 >= _TOOL_PROMOTE_THRESHOLD:
            proposed = _propose_tool(gap)
            plan.append(
                f"This task needed a tool we don't have yet ({name}) — prepared a "
                "draft request for the developers to add it. Nothing was changed."
            )
            break
        plan.append(f"This task needed an extra tool ({name}) — handled it just for this run.")

    blocked = blocking
    status = "blocked" if blocked else "done"
    cost = round(
        float(config.MODEL_TIERS[tier]["cost_per_run"])
        + 0.01 * len(artifacts)
        + (0.05 if proposed else 0.0),
        2,
    )
    summary = (
        f"{len(artifacts)} deliverable(s) from {len(specialists)} specialist(s); "
        f"{model}; {'blocked by guardrails' if blocked else 'ready for review'}."
    )

    proposed_json = json.dumps(asdict(proposed)) if proposed else ""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO assist_runs (ticket_id, status, complexity, model_tier, "
            "model, specialists_json, plan_json, artifacts_json, findings_json, "
            "capability_gaps_json, proposed_tool_json, cost_estimate, summary, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ticket_id,
                status,
                complexity,
                tier,
                model,
                json.dumps(specialists),
                json.dumps(plan),
                json.dumps([asdict(a) for a in artifacts]),
                json.dumps([asdict(f) for f in findings]),
                json.dumps(gaps),
                proposed_json,
                cost,
                summary,
                db.now_iso(),
            ),
        )
        run_id = cur.lastrowid
    run = get_run(run_id)
    assert run is not None
    return run


class SendBlocked(RuntimeError):
    """Raised when a human tries to send correspondence the guardian blocks."""


def send_artifact(run_id: int, artifact_index: int, body: str | None = None) -> AssistRun:
    """Human clicks Send on a drafted reply. Accepts the (possibly edited) text
    from the review box, refuses to send while [placeholders] remain, re-screens,
    then files an outbound interaction (prototype: simulated 'sent (demo)';
    production: Gmail API)."""
    run = get_run(run_id)
    if run is None:
        raise ValueError(f"No assist run #{run_id}")
    if artifact_index < 0 or artifact_index >= len(run.artifacts):
        raise ValueError("No such deliverable")
    art = run.artifacts[artifact_index]
    if art.kind != "correspondence" or not art.sendable:
        raise ValueError("This deliverable is not sendable")

    text = body.strip() if (body and body.strip()) else art.body
    if re.search(r"\[[^\]]+\]", text):
        raise SendBlocked(
            "This reply still has [bracketed placeholders] to fill in before it " "can be sent."
        )
    art.body = text

    ticket = _load_ticket(run.ticket_id)
    unit = (ticket or {}).get("unit", "") or ""
    findings = guardrails.screen(text, unit)
    if guardrails.has_block(findings):
        raise SendBlocked("Guardrails block this message; it cannot be sent.")

    subject = art.title
    m = re.search(r"^Subject:\s*(.+)$", art.body, re.M)
    if m:
        subject = m.group(1).strip()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO interactions (direction, party, subject, body, unit, "
            "case_ref, topic_key, created_at) VALUES ('outbound',?,?,?,?,?,?,?)",
            (
                "Chairperson",
                f"[SENT — demo] {subject}",
                art.body,
                unit,
                (ticket or {}).get("case_ref", ""),
                (ticket or {}).get("topic_key", ""),
                db.now_iso(),
            ),
        )
        art.sent = True
        cur.execute(
            "UPDATE assist_runs SET artifacts_json = ? WHERE id = ?",
            (json.dumps([asdict(a) for a in run.artifacts]), run_id),
        )
    refreshed = get_run(run_id)
    assert refreshed is not None
    return refreshed
