# Agent Roster (re-scoped, trustees-only platform)

**Date:** 19 June 2026
**Status:** Proposed — pending Chairperson approval (Vision §8 open item 1)
**Companions:** [VISION_AND_REQUIREMENTS.md](VISION_AND_REQUIREMENTS.md) (the _what_) · [AI_NATIVE_BUILD_PLAN.md](AI_NATIVE_BUILD_PLAN.md) (the _how_) · supersedes the 10-agent roster in [SOLUTION_DESIGN.md](SOLUTION_DESIGN.md) §7.

> **Why re-scope?** The original roster (SOLUTION*DESIGN §7) assumed a single-trustee \_email proxy* for "The Wilds Estate" with full operational finance and a statutory compliance calendar. The v2 vision is a **trustees-only platform for one scheme**, where finance is **oversight-only and post-MVP**, compliance is **lean**, and a **task board + document brain** are first-class. This roster collapses redundant specialists, drops scheme-branded agents, and adds the three workers the MVP triad actually needs.

---

## 1. Design principles

1. **An "agent" = a Lambda with a scoped system prompt + a typed, allow-listed MCP toolset** (per [AI_NATIVE_BUILD_PLAN.md](AI_NATIVE_BUILD_PLAN.md) §2 G6). No agent has tools outside its list.
2. **Haiku-first.** Cheap model for classify/file/ticket; escalate to Sonnet only for legal/financial reasoning and complex drafting.
3. **Every outbound-money / signature / email action is human-gated** (Vision §2 hard line), with the **sole carve-out** of bare acknowledgements (Vision §7).
4. **Earned autonomy = N = 3** approved runs per intent, no intervening rejection (Vision §4.10).
5. **Cross-cutting guardrails wired from day one:** resolution-gate hard-block, conflict self-declaration, the five no-gos, defamation advisory screen, global kill-switch, dry-run mode.
6. **The accountable human is always the Chairperson** (Vision §3).

---

## 2. The roster at a glance

| #   | Agent                           | Type                        | Phase    | Model          | Default autonomy tier            |
| --- | ------------------------------- | --------------------------- | -------- | -------------- | -------------------------------- |
| 1   | **Orchestrator**                | Step Functions (not an LLM) | MVP      | —              | n/a (state machine)              |
| 2   | **Intake Classifier**           | Pipeline (event)            | MVP      | Haiku          | 1 — auto-classify                |
| 3   | **Draft Composer**              | Pipeline (event)            | MVP      | Haiku → Sonnet | 0 — draft-and-approve            |
| 4   | **Records Clerk** (filing)      | Pipeline (event)            | MVP      | Haiku          | 2 — auto-file (earned)           |
| 5   | **Ticketing Agent**             | Pipeline (event)            | MVP      | Haiku          | 1 → 2 — auto-ticket (earned)     |
| 6   | **Governance Guardian**         | Guardrail (inline)          | MVP      | Haiku + policy | n/a (always-on gate)             |
| 7   | **Trustee Copilot**             | Interactive (chat)          | MVP      | Sonnet         | 0 — gated actions only           |
| 8   | **Legal & Compliance Analyst**  | Pipeline / on-demand        | Post-MVP | Sonnet         | 0 — advisory                     |
| 9   | **Financial Oversight Analyst** | On-demand / scheduled       | Post-MVP | Sonnet         | 0 — advisory                     |
| 10  | **Maintenance Coordinator**     | Pipeline / on-demand        | Post-MVP | Haiku          | 1 — log/track                    |
| 11  | **Knowledge Auditor**           | Scheduled (batch)           | Post-MVP | Haiku → Sonnet | n/a (advisory, never auto-edits) |

**MVP set = agents 1–7** (delivers the Vision §6 triad). **Post-MVP = agents 8–11** (finance, deeper legal/compliance, maintenance, KB hygiene).

---

## 3. MVP agents

### 1. Orchestrator _(Step Functions — not an LLM)_

- **Job:** route work, hold workflow state, manage the human-in-the-loop **task-token** pause/resume, enforce iteration & token-budget caps, honour the **global kill-switch**.
- **Triggers:** EventBridge (new email, new upload, new ticket event, Copilot action).
- **Tools:** invokes the other agents; writes state to DynamoDB. No model, no autonomy of its own.
- **Why not an LLM:** routing/state must be deterministic and auditable; the LLM reasoning lives in the worker agents.

### 2. Intake Classifier

- **Job:** parse each inbound email → `{intent, priority, party, entities, unit?, case_id?, language}`; link to an existing case-file/unit-file or open a new matter.
- **Trigger:** Gmail ingestion event.
- **Typed tools (allow-list):** `read_inbound_message`, `lookup_case`, `lookup_unit`, `create_case` (draft state), `emit_classification`.
- **Autonomy:** **Tier 1** — classification is low-risk and reversible; it never communicates outward.
- **No-go alignment:** cannot draft or send anything; classification only.

### 3. Draft Composer

- **Job:** produce grounded outbound drafts — replies, owner circulars, conduct-breach notices, contractor instructions, minutes/resolutions — **concise, warm, natural** (Vision §4.11), grounded on the document brain.
- **Trigger:** Orchestrator, after classification/retrieval; or Copilot request.
- **Typed tools:** `query_knowledge_base`, `query_interaction_store`, `get_case_file`, `get_unit_file`, `compose_draft` (writes a **pending** draft only).
- **Autonomy:** **Tier 0** — always draft-and-approve. **Sole exception:** bare acknowledgements may auto-send once the _acknowledgement_ intent has earned Tier 1 (N = 3).
- **Guardrails:** every draft passes the **Governance Guardian** (resolution-gate + defamation screen + no-gos) before it reaches the approval tray. Model escalates Haiku→Sonnet for legal/financial or bulk-comms drafts.

### 4. Records Clerk (filing / document brain writer)

- **Job:** ingest scheme documents into the **Authoritative Knowledge Base** and file every interaction into the **Interaction Store** — auto-tagged (case, unit, category, financial year), versioned by effective date, embedded for RAG (Vision §4.4–4.5).
- **Trigger:** new upload; every sent/received message; resolution registered.
- **Typed tools:** `store_kb_document`, `store_interaction`, `tag_record`, `link_to_case`, `link_to_unit`, `embed_for_rag`. **No outbound, no delete** (retention = forever).
- **Autonomy:** **Tier 2 (earned)** — auto-files after N = 3 correctly-filed runs per record-type; before that, filing decisions surface for one-click confirm. Mis-files are re-tagged, never destroyed.

### 5. Ticketing Agent

- **Job:** turn inbound issues/emails into **board tickets** — create, classify (maintenance / compliance / complaint / financial / governance / dispute), assign to the right portfolio role, set due dates, and **link to case/unit/document/resolution** (Vision §4.12).
- **Trigger:** classified inbound message; Copilot request.
- **Typed tools:** `create_ticket`, `assign_ticket`, `set_due_date`, `link_ticket`. Tickets from agents start in a **Suggested** tray (mitigates task-injection) until the intent earns Tier 2.
- **Autonomy:** **Tier 1 → 2 (earned)** — proposes tickets immediately; auto-commits them to the board after N = 3 accepted suggestions per issue-type.

### 6. Governance Guardian _(always-on guardrail, not a worker)_

- **Job:** the **hard safety layer** every action passes through before it can leave draft state. Enforces:
  - **Resolution-gate hard-block** — refuse to action anything requiring a signed trustee resolution that isn't in the resolution register (the Kiepersol failure).
  - **Conflict self-declaration prompt** — at each decision, prompt affected trustees to declare interest (the "Margaret = Unit 2 owner" scenario).
  - **The five no-gos** (Vision §4.9) — block legal demands/threats, naming individuals at-fault, direct external contact (CSOS/lawyers), reserve-fund authorisation, and bulk comms without approval.
  - **Defamation/privilege screen** — **advisory warn** on outbound, human decides.
  - **Reserve-fund PMR-24 guard** (activates with the finance phase).
- **Trigger:** inline on every draft/ticket/action.
- **Typed tools:** `check_resolution_register`, `check_conflict`, `screen_outbound`, `block_or_warn`. It can **block** and **annotate**; it can never send or approve.
- **Autonomy:** n/a — it is a gate, not an autonomous actor, and is **exempt from the kill-switch** (safety must not be switchable off).

### 7. Trustee Copilot _(the only agent a human chats with)_

- **Job:** in-app conversational front door — answers "why/what" grounded on the KB + case/unit files, and can **initiate** actions (draft a reply, open a case, create a ticket, schedule a reminder) that route through the **same approval loop** as the pipeline.
- **Trigger:** trustee chat in the dashboard.
- **Typed tools:** read tools across the document brain + board; **write tools only produce pending/draft artefacts** tagged `via=copilot`.
- **Autonomy:** **Tier 0** — every action it initiates is gated; it never sends email or moves money. RBAC-bounded retrieval (a finance-portfolio trustee sees finance; etc.).

---

## 4. Post-MVP agents

### 8. Legal & Compliance Analyst _(merges old Legal Analyst + Compliance Tracker; drops "Wilds Estate Specialist")_

- **Job:** STSMA / PMRs / Conduct Rules / CSOSA / **this scheme's rules** reasoning; maintain the **lean deadline list**; flag governance/eligibility issues.
- **Why merged:** single scheme → no separate "estate specialist"; scheme rules live in the KB and are served here + via Copilot. Compliance is lean (Vision §4.7), so a full statutory-calendar agent is unwarranted.
- **Autonomy:** **Tier 0** — advisory only; never contacts CSOS/lawyers (no-go #3).
- **Tools:** `query_knowledge_base`, `query_precedent_db`, `list_deadlines`, `flag_compliance_item`.

### 9. Financial Oversight Analyst _(re-scoped from old Financial Analyst — oversight, not accounting)_

- **Job:** ingest the **MA files the Chairperson periodically uploads** (Vision §4.2 confirmed), then provide financial overview/health, scenario planning, **separate Reserve vs Admin** tracking, reserve-contribution modelling, draft annual budget, draft & track the **10-year maintenance plan**. Computes **arrears interest only at a resolution-backed rate**.
- **Hard limits:** **never moves money**, never authorises reserve-fund use (no-go #4 / PMR-24 guard via Governance Guardian), never replaces the MA's book of record.
- **Autonomy:** **Tier 0** — advisory; all figures presented for human action.
- **Tools:** `ingest_ma_export`, `read_financial_figures`, `model_reserve`, `draft_budget`, `compute_arrears_interest` (resolution-rate-checked).

### 10. Maintenance Coordinator _(leaner than old Maintenance Specialist)_

- **Job:** log/track maintenance issues, keep a simple contractor contact list, **store quotes the trustee collects**, track 10-year-plan-vs-actual drift, classify **common-property vs private/EUA** for routing, schedule cyclical maintenance (Vision §4.6).
- **Autonomy:** **Tier 1** — logging/tracking is low-risk; any contractor _instruction_ is a Draft Composer + human-send action, not autonomous.
- **Tools:** `log_maintenance_issue`, `track_plan_drift`, `store_quote`, `classify_property_area`, `schedule_cyclical`.

### 11. Knowledge Auditor _(scheduled, advisory — unchanged in spirit)_

- **Job:** periodic scan for stale/superseded/contradictory docs and coverage gaps; emits a prioritised **action list** for human review.
- **Hard limit:** **never auto-edits** the authoritative corpus (Vision §4.11).
- **Autonomy:** n/a — batch job, advisory output only.
- **Tools:** `scan_kb`, `detect_contradictions`, `emit_audit_report` (read + report; no write to authoritative docs).

---

## 5. Mapping to the original 10-agent roster

| Original (SOLUTION_DESIGN §7) | Fate in v2                                                     | Reason                                                         |
| ----------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| 1. Orchestrator               | **Kept** (1)                                                   | Deterministic routing/state still needed.                      |
| 2. Email Classifier/Router    | **Kept** → Intake Classifier (2)                               | Core of the email workflow.                                    |
| 3. Legal Analyst              | **Merged** → Legal & Compliance Analyst (8), post-MVP          | Combined with Compliance; deferred past MVP.                   |
| 4. Financial Analyst          | **Re-scoped** → Financial Oversight Analyst (9), post-MVP      | Oversight-only, no money movement; post-MVP.                   |
| 5. Compliance Tracker         | **Merged** into (8)                                            | Compliance is now lean (deadline list).                        |
| 6. Draft Composer             | **Kept** (3)                                                   | Central to the draft-and-approve loop.                         |
| 7. Wilds Estate Specialist    | **Dropped**                                                    | Single scheme; scheme rules live in the KB, served by (8)/(7). |
| 8. Maintenance Specialist     | **Re-scoped** → Maintenance Coordinator (10), post-MVP, leaner | No full procurement; log/track + quotes.                       |
| 9. Trustee Copilot            | **Kept** (7)                                                   | Only interactive agent; first-class in MVP.                    |
| 10. Knowledge Auditor         | **Kept** (11), post-MVP                                        | Advisory hygiene, never auto-edits.                            |
| —                             | **NEW: Records Clerk (4)**                                     | The document-brain _writer_ the two-store model needs.         |
| —                             | **NEW: Ticketing Agent (5)**                                   | The task-board product needs AI auto-ticketing.                |
| —                             | **NEW: Governance Guardian (6)**                               | Makes the resolution-gate / no-gos a concrete enforced layer.  |

**Net:** 10 → 11 agents, but the **MVP runs on 7**, finance/legal/maintenance/audit deferred, and the scheme-branded specialist removed.

---

## 6. Autonomy & guardrail summary

- **Tier 0 (draft-and-approve):** Draft Composer, Trustee Copilot, Legal & Compliance Analyst, Financial Oversight Analyst — anything that talks to humans or touches money/legal.
- **Tier 1 (auto, low-risk):** Intake Classifier, Maintenance Coordinator; Draft Composer's _acknowledgement_ intent after earning.
- **Tier 2 (earned, N = 3):** Records Clerk auto-filing, Ticketing Agent auto-commit — internal, reversible actions only.
- **Never automated:** the five no-gos, signed-resolution-gated actions, reserve-fund authorisation, bulk owner comms, any signature, any money movement.
- **Always-on / un-switchable:** Governance Guardian.
- **Globally switchable off:** every Tier 1/2 behaviour via the kill-switch; on trip, all agents fall back to Tier 0 draft-only.

---

## 7. Sub-decisions — APPROVED (19 June 2026)

1. **7-agent MVP set (1–7)** — APPROVED as the first product increment after P0 foundations.
2. **Records Clerk at Tier 2** — APPROVED (auto-file after N = 3; mis-files re-tagged, never deleted).
3. **Ticketing auto-commit** — APPROVED ("Suggested tray → earn Tier 2" path).
4. **Governance Guardian kill-switch exemption** — APPROVED (safety gate stays on even when autonomy is frozen).
