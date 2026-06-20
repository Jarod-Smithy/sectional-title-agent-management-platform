# Sectional Title Platform — Vision & Requirements (v2, post re-interview)

**Date:** 19 June 2026
**Status:** Draft for build — supersedes the scope assumptions in [SOLUTION_DESIGN.md](SOLUTION_DESIGN.md) where they conflict
**Source:** Structured 16-domain stakeholder interview (Chairperson & Trustee). Captured verbatim decisions, re-scoped from the original "email proxy for one trustee" toward a leaner, trustees-only platform.

> This document records **what we are building and why**. The **how** (delivery, guardrails, agents) is in [AI_NATIVE_BUILD_PLAN.md](AI_NATIVE_BUILD_PLAN.md).

---

## 1. Vision

A **trustees-only**, AI-native platform that does two jobs for a single sectional title body corporate:

1. **Agentic trustee assistant** — acts as the Chairperson's personal assistant, automating trustee work: triaging inbound correspondence, drafting documents and replies, planning, and keeping records.
2. **Trustee operations platform** — a Jira-style **task board + issue-tracker**, a **document brain** (knowledge base + correspondence ledger), **financial oversight**, and **governance guardrails**.

The platform **augments the trustees and absorbs the board's operational admin**, sitting as an **independent oversight layer above the managing agent** — precisely the independent visibility and governance that was missing in the Kiepersol Park matter.

**Success in 12 months:** the platform reliably does the Chairperson's routine trustee work (assistant) _and_ provides the agentic platform for trustee tasks, process, planning, documentation management and issue-tracking.

---

## 2. Scope

| Dimension                                                                   | Decision                                                                                                              |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Schemes                                                                     | **Single scheme only** (no multi-tenancy required)                                                                    |
| Users with logins                                                           | **Chairperson + other trustees ONLY**                                                                                 |
| Everyone else (owners, tenants, managing agent, contractors, CSOS, auditor) | **Email only — no logins**                                                                                            |
| Primary role                                                                | Augments trustees **+** replaces the board's operational work                                                         |
| Relationship to managing agent                                              | Platform is the trustees' **oversight/planning layer**; the MA keeps the financial book of record and moves all money |

### Out of scope / explicitly the human's job (hard line)

- **All outbound emails** (except bare acknowledgements — see §7).
- **Anything requiring a signature.**
- **Anything that moves money** (the managing agent does this).

---

## 3. Accountability & success metrics

- **Accountable human for every AI action:** always the **Chairperson**.
- **Top success metrics:** (1) trustee hours saved/month; (2) % of emails auto-handled correctly; (3) zero missed compliance deadlines; (4) owner satisfaction / response time.

---

## 4. Functional requirements by domain

### 4.1 Users, roles & access

- Logins for **Chairperson + trustees** only.
- **Per-portfolio scoped roles**: finance, maintenance, security, secretary.
- Owners/tenants/MA/contractors interact **by email only**.
- The PM/issue-tracker is a **private trustees-only board workspace**.

### 4.2 Financial oversight (NOT operational accounting)

- The managing agent handles **all payment instructions and fund collection**; the platform **reads** the MA's figures (MA system stays the book of record).
- **How MA figures arrive (confirmed):** the Chairperson **periodically downloads the relevant files from the MA platform and uploads them** to this platform (manual export/upload — no live feed/integration). The platform ingests, parses and indexes them for oversight.
- Platform provides: **financial overview, financial health, scenario planning**, accurate tracking of **Reserve + Administrative funds** separately, and **maintenance-plan recommendations**.
- **Reserve fund:** flag/block use that is not compliant with PMR 24.
- **Arrears interest:** compute **only** at a rate backed by a **signed trustee resolution** (the exact Kiepersol failure).
- **Arrears ladder:** auto-draft reminder → demand → final notice, then **STOP before legal handover** (human sends).
- **No payment handling at all.**
- Produce: draft **annual budget**, draft & track **10-year maintenance/repair/replacement plan**, model **reserve-fund contributions**. (Monthly accounts & auditor pack remain the MA's job.)

### 4.3 Meetings & governance

- **Ingest AGM/SGM notes**, store for record, queryable via agentic RAG (the platform does **not** convene meetings or manage agendas).
- **Draft minutes** from a recording/transcript, route for approval.
- **HARD BLOCK:** refuse to action any decision lacking a properly **signed trustee resolution**.
- **Resolution register** = single source of truth (every resolution, votes, signed PDF, effective date).
- **Conflicts of interest:** **prompt trustees to self-declare** at each decision (the Kiepersol "Margaret = Unit 2 owner" scenario).
- Maintain **office-bearer register**, **trustee elections/eligibility**, **round-robin/written resolutions**.
- Quorum/proxy/voting mechanics: **not needed**.

### 4.4 Records, documents & filing — the "document brain"

- **Draft:** minutes & resolutions, conduct-rule breach notices, contractor instructions/scopes, CSOS dispute forms, owner circulars.
- **Store & index (official record):** founding docs/sectional plans/rules, insurance policy & valuations, audited financials/management accounts, contracts (MA, contractors), all correspondence, resolutions & minutes.
- **Retention:** keep everything **forever**.
- **Versioning:** version history **queryable by effective date** ("which rules applied on 3 Mar 2024").
- **Filing:** multi-faceted tags (case, unit, category, financial year).
- **Per-unit file** aggregating owner, levy history, breaches, correspondence, transfers.
- **Storage:** standard encrypted storage (tamper-evident/hash-chain **not** required).

### 4.5 Two-store architecture (decided during interview)

1. **Authoritative Knowledge Base** (RAG corpus) — statutes, PMRs/Conduct Rules, CSOSA, scheme rules, minutes, financials, insurance, contracts, CSOS adjudication orders. Versioned, citable.
2. **Interaction Store** (correspondence ledger) — every email, WhatsApp, call note and letter (trustee↔trustee, owner→trustee, trustee↔external). Each stored as a timeline event, **auto-filed to both the relevant case-file and unit-file**, tagged by party, and embedded for agentic RAG. **Per-unit and case files are views over this store.**

### 4.6 Maintenance & vendors (lightweight)

- **Log & track** maintenance issues (not a full procurement workflow).
- **Simple contractor contact list**; **store quotes** the trustee collects.
- **Track the 10-year plan vs actual spend** and flag drift.
- **Classify common-property vs private/exclusive-use-area** to route responsibility.
- **Schedule preventive/cyclical** maintenance (fire equipment, gates, pumps, paint cycles).

### 4.7 Compliance (lean)

- **Simple deadline list** (not a full escalation calendar).
- **Store** insurance policy; **CSOS annual returns not required**.
- **POPIA:** keep the platform's own data POPIA-safe; **no owner-facing POPIA workflow**.
- No OHS/municipal/fire/SARS workflows for now.

### 4.8 Communications

- Channels: **email** (inbound parsing + draft outbound) + **WhatsApp** (notify the trustee of pending items).
- Outbound voice: **as from the Chairperson personally** (reviewed & sent by a human).
- Language: **English only**.
- **Bulk owner comms:** may be drafted, but **mandatory legal-risk screen + human approval** before sending (the Kiepersol defamation risk).
- **Per-issue case-file threading** groups all related comms under one matter.
- **Auto-send carve-out:** only **bare acknowledgements** ("we've received your message") may auto-send; anything substantive stays human-sent.

### 4.9 Disputes, legal & risk guardrails

- **Track dispute status & store documents** (do not encode the full CSOS process).
- **Defamation/privilege screening** on outbound = **warn the user, user decides** (advisory, not a hard block).
- **Absolute no-gos (the AI must NEVER do autonomously):**
  1. Issue legal demands/threats.
  2. Name an individual as negligent/at-fault.
  3. Contact CSOS / lawyers / external parties directly.
  4. Authorise reserve-fund use.
  5. Send bulk owner comms without approval.
- Legal documents stored normally (no privilege-flag workflow).

### 4.10 Agent design & autonomy (AI-native safety stack — all adopted)

- **Per-intent autonomy tiers:** auto / draft-and-approve / human-only (configurable).
- **Earned/graduated autonomy:** an action graduates to auto only after **N = 3 successful approved runs** (confirmed) for that intent, with no intervening rejection.
- **Typed, permissioned MCP tools:** every tool call logged & policy-checked.
- **Dry-run / simulation mode** before going live.
- **Global kill-switch** to freeze all autonomous action.
- **Agent roster:** to be recommended by the build plan (re-scoped from the original 10-agent design).

### 4.11 Knowledge, learning & evaluation

- Corpus per §4.5(1) incl. CSOS precedent.
- **Citations:** nice-to-have; the assistant should answer anyway, keeping responses **concise, warm and natural**.
- **Scheduled Knowledge Auditor:** flags stale/superseded/contradictory docs; **never auto-edits**.
- **Precedent database** of past decisions + **confidence scores**; auto-escalate low-confidence items.
- **Evaluation bar:** lighter — **manual spot-check** (no formal golden-set gate for the product agents).
- **Learning:** few-shot examples + **dynamic skill updates** from the Chairperson's corrections.

### 4.12 Issue-tracker / PM product

- **Trustee Kanban board + issue-tracking.**
- **AI auto-creates tickets from inbound emails/issues**, assigns them, and sets due dates.
- **Tickets link to** case files, units, documents and resolutions.
- Issue types: maintenance, compliance, owner complaints/conduct breaches, financial actions, governance, disputes/legal.

---

## 5. Non-functional requirements

| Requirement       | Decision                                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------- |
| Data residency    | **South Africa (af-south-1)**                                                                         |
| LLM               | **Claude via AWS Bedrock** (in-account; **no PII to public third-party LLM APIs**)                    |
| Hosting           | **AWS serverless** (Lambda + Step Functions), **cost-optimised on free tiers** (personal credit card) |
| Budget posture    | Middle ground between ~$45/mo and near-zero free-tier-only                                            |
| Auth              | **AWS Cognito** (free tier, RBAC, MFA)                                                                |
| PII               | Encryption + log redaction; never log PII                                                             |
| Audit             | Full audit trail of every AI decision/action                                                          |
| Availability / DR | Best-effort; RPO/RTO 24–48h                                                                           |

---

## 6. MVP definition

The MVP must prove **three workflows together**:

1. **Inbound email → grounded draft → human approve/send → auto-file + ticket.**
2. **Document brain** — ingest and agentic-RAG-query all scheme documents and interactions.
3. **Trustee task board + issue-tracking** (with AI auto-ticketing from email).

**Financial oversight** (reserve/admin health, scenario planning, maintenance planning) is the **next phase after MVP**.

**Delivery approach:** **P0 AI-native SDLC foundations/guardrails first, then agents** (see [AI_NATIVE_BUILD_PLAN.md](AI_NATIVE_BUILD_PLAN.md)).

---

## 7. Key changes vs. the original SOLUTION_DESIGN.md

| Topic          | Original design                                                 | This v2                                                         |
| -------------- | --------------------------------------------------------------- | --------------------------------------------------------------- |
| Audience       | Email proxy for one trustee                                     | **Trustees-only platform** (multiple trustees, scoped roles)    |
| Second product | —                                                               | **Jira-style PM/issue-tracker** is a first-class function       |
| Finance        | Levy calc, arrears, budgets implied as platform-run             | **Oversight only** above the MA; **no money movement**          |
| Languages      | English + Afrikaans + OCR                                       | **English only** (simpler pipeline)                             |
| Compliance     | Full statutory calendar, CSOS returns, insurance, POPIA officer | **Lean**: deadline list, store policies, internal POPIA hygiene |
| Email autonomy | Auto-send low-risk replies                                      | **Only bare acknowledgements** auto-send                        |
| Conflicts      | (not addressed)                                                 | **Self-declaration prompt** + resolution-gated actions          |
| Multi-tenancy  | RBAC for trustees                                               | Single scheme; trustees-only RBAC                               |

---

## 8. Open items to confirm before/early in build

1. Final **agent roster** — **proposed in [AGENT_ROSTER.md](AGENT_ROSTER.md)** (pending your approval).
2. Exact **WhatsApp** provider/timing (deferred from MVP integrations — Gmail only in MVP).
3. ~~How the **MA financial figures** are obtained~~ — **CONFIRMED:** Chairperson periodically downloads files from the MA platform and **uploads** them (manual export/upload; no live feed).
4. ~~Definition of **"N successful runs"**~~ — **CONFIRMED: N = 3** approved runs per intent, no intervening rejection.
