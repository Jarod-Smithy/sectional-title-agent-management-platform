# Specialist Agent Assist → AWS Bedrock AgentCore mapping

> How the prototype's on-demand "Get agent help" feature maps onto AWS Bedrock
> **AgentCore** in production. The prototype is deliberately built as a faithful
> _seam_: every place it does a local, offline stand-in is the place a managed
> AgentCore capability slots in, with no change to the UX or the data contract.

See the working prototype in [`prototype/app/specialists.py`](../prototype/app/specialists.py),
[`prototype/app/threads.py`](../prototype/app/threads.py) and
[`prototype/app/config.py`](../prototype/app/config.py).

---

## 1. What the feature does

Each task on the board has a **Get agent help** button. When the Chairperson
clicks it, an **Orchestrator** reads the task title/details, dynamically routes
it to one or more specialist agents, sizes the work to pick the cheapest capable
reasoning model, and produces **drafts/suggestions** the human reviews — never
actions. Any actionable output (e.g. correspondence) is screened by the
Governance Guardian, and only the human can Send, sign or move money.

Core principles (unchanged from prototype to production):

- **On-demand, human-triggered** — an explicit per-task click, plus a global
  enable flag and a kill-switch (cost control).
- **Suggest, never act** — output is always a reviewable draft.
- **Capability manifest** — the agent only does what it is declared allowed to
  do; anything else becomes a _proposed permanent tool_ via a draft PR.
- **Human is accountable** — assignee is always the Chairperson; emails,
  signatures and payments are human-only.

---

## 2. Component mapping

| Prototype (offline, stdlib)                     | Production (AWS Bedrock AgentCore)                                                                                   |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `specialists.run_assist()` orchestrator         | **AgentCore Runtime** — serverless, session-isolated agent hosting (the orchestrator + sub-agents run here)          |
| `route()` keyword scoring                       | Orchestrator agent reasoning (a model call that selects specialists)                                                 |
| `assess_complexity()` → model tier              | Same heuristic as a pre-filter, then the orchestrator confirms model choice                                          |
| `_calc_*` real stdlib calculations              | **AgentCore Code Interpreter** — sandboxed Python for levy interest, reserve projections, budgets, quote comparisons |
| `_research_brief()` placeholder shortlist       | **AgentCore Browser** — headless, governed web browsing to fetch live candidates/sources                             |
| `rag.search()` over local SQLite                | **AgentCore Gateway (MCP)** → document brain, resolution register, interaction ledger as governed MCP tools          |
| `config.CAPABILITIES` manifest                  | Tool allow-list enforced at the Gateway + agent policy                                                               |
| `threads.assign_topic_key()`                    | **AgentCore Memory** — long-term, topic-keyed memory shared across a matter                                          |
| `guardrails.screen()`                           | Same logic as an AgentCore guardrail / Bedrock Guardrails policy invoked before any send                             |
| `_propose_tool()` simulated draft PR            | **GitHub App** + CI: the agent opens a real _draft_ PR (human-merge, CI-gated)                                       |
| `send_artifact()` → `[SENT — demo]` interaction | **Gmail API** (or SES) send, recorded in the interaction ledger                                                      |
| `config.RUNTIME` enable/kill flags              | Control-plane flag (SSM Parameter / AppConfig) + AgentCore session quotas                                            |
| `assist_runs` SQLite table                      | DynamoDB run log + **AgentCore Observability** traces                                                                |

---

## 3. Model tiering → Bedrock model IDs

The Orchestrator sizes each task and picks the cheapest capable model. The tier
and model are recorded on every run and shown on the artifact.

| Tier       | When                                                   | Bedrock model ID (target)                   | Indicative cost/run |
| ---------- | ------------------------------------------------------ | ------------------------------------------- | ------------------- |
| `fast`     | Simple, single-step, no compute/research               | `anthropic.claude-3-5-haiku-20241022-v1:0`  | ~$0.01              |
| `balanced` | Some compute or research, moderate length              | `anthropic.claude-3-7-sonnet-20250219-v1:0` | ~$0.06              |
| `deep`     | Multi-specialist, multi-step, heavy compute + research | `anthropic.claude-opus-4-20250514-v1:0`     | ~$0.30              |

Defined in [`prototype/app/config.py`](../prototype/app/config.py) (`MODEL_TIERS`).
Cost discipline: the prototype refuses to run when disabled/kill-switched and
estimates a per-run cost; production adds AgentCore session quotas and budget
alarms.

---

## 4. The capability manifest (allow-list)

The agent consults a declared manifest before acting (`config.CAPABILITIES`):

- **read** — `document_brain`, `resolution_register`, `interaction_ledger`, `ticket`
- **draft** — `resolution_template`, `correspondence`, `action_plan`, `research_brief`, `owner_circular`
- **compute** — `levy_interest`, `reserve_projection`, `budget_model`, `quote_comparison`

If a task needs something **outside** the manifest (e.g. `compute:csos_dispute_pack`),
the agent does **not** improvise an ungoverned action. Instead:

1. It uses a temporary, throwaway tool (Code Interpreter scratch) for this run, and
2. If the need recurs, it **proposes a permanent MCP tool** by opening a draft
   pull request that adds the tool under `tools/mcp/` and registers the capability.

In production this is the _self-improvement loop_: AgentCore detects a recurring
gap, generates the tool via the GitHub App, and CI + a human reviewer gate the
merge. The agent can author, but **cannot merge** — durable, governed tools live
as MCP/Gateway tools, not as ad-hoc code.

### Why Code Interpreter vs MCP/Gateway

- **Code Interpreter** = ephemeral scratch compute for _this_ run (safe sandbox,
  no persistence, no new surface area).
- **MCP/Gateway tool** = a _durable, reviewed, governed_ capability with an audit
  trail. Recurring scratch work is promoted here via PR — that is the only way a
  new capability becomes permanent.

---

## 5. Cross-thread topic consolidation → AgentCore Memory

Owners raise the same matter across different email threads. `threads.py`
assigns a stable `topic_key` by fuzzy-matching new mail against existing mail on
subject (Re:/Fwd:-stripped Jaccard), participant, and content similarity. Tasks
carry their matter's `topic_key`, so the board shows **related correspondence
across threads** and the agent reasons over the whole matter at once.

In production this is **AgentCore Memory**, keyed by topic, so the agent has the
full history of a matter regardless of how the mail was threaded.

---

## 6. Output landing & the human-in-the-loop

- Deliverables are **attached to the task** and **reviewable from the task**.
- Correspondence is **sendable from the UI** — the human clicks Send. The
  prototype simulates `sent (demo)` and files an outbound interaction; production
  calls the Gmail API. Bare acknowledgements may still auto-file (the existing
  H56 carve-out).
- Every send is **re-screened** by the Governance Guardian server-side, so an
  edit can never bypass the gate.

---

## 7. Safety & guardrails (unchanged across environments)

- Assignee is always the **Chairperson**; the agent suggests, the human acts.
- Governance Guardian screens any actionable output before it can be sent.
- The agent never sends email, signs resolutions, or moves scheme funds.
- Global **enable flag** + **kill-switch** + explicit per-task trigger.
- Self-improvement PRs are **draft only**, human-merge, CI-gated. In the offline
  prototype this is _simulated_ — nothing is ever pushed to GitHub.

---

## 8. Reference: API surface (prototype)

| Method & path                    | Purpose                                                  |
| -------------------------------- | -------------------------------------------------------- |
| `POST /api/tickets/{id}/assist`  | Run the specialist team once for a task                  |
| `GET /api/tickets/{id}/assist`   | List prior assist runs for a task                        |
| `GET /api/tickets/{id}/threads`  | Related correspondence across threads (same matter)      |
| `POST /api/assist/{run_id}/send` | Human sends a drafted reply (re-screened)                |
| `GET /api/assist/config`         | Global enable / kill-switch / model tiers / capabilities |
| `POST /api/assist/config`        | Toggle the global enable flag or kill-switch             |

These map 1:1 onto API Gateway routes fronting Lambda → AgentCore Runtime in the
production design.
