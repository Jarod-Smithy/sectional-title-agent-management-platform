# AI-Native SDLC Design — Sectional Title AI Agent Platform

**Version**: 0.1 (Draft — Spec for validation)
**Date**: 15 June 2026
**Companion to**: [SOLUTION_DESIGN.md](./SOLUTION_DESIGN.md)
**Status**: Layer 1 spec — pending stakeholder validation **before** any repo/hook scaffolding
**Purpose**: Define a self-developing software factory where specialized AI agents own the full software development lifecycle (SDLC) of the property platform — spec → code → review → security → test → release — with an in-app, admin-only intake and human approval only at the production-deploy boundary.

> This document follows the same **3-Layer Karpathy method** used for the product design: **Layer 1 (Spec)** = this blueprint; **Layer 2 (Verifier)** = the quality gates and eval harness; **Layer 3 (Environment)** = the repo, hooks, and runtime guardrails. No code or repos are created until this spec is validated.

---

## Table of Contents

1. [Goal & Decision Driven](#1-goal--decision-driven)
2. [Confirmed Decisions](#2-confirmed-decisions)
3. [Key Tensions & Compensating Controls](#3-key-tensions--compensating-controls)
4. [Architecture Overview](#4-architecture-overview)
5. [Dev-Agent Roster](#5-dev-agent-roster)
6. [Repository Topology (Recommendation)](#6-repository-topology-recommendation)
7. [End-to-End Workflow](#7-end-to-end-workflow)
8. [In-App Dev Console & Intake Bridge](#8-in-app-dev-console--intake-bridge)
9. [Pre-Commit Hooks](#9-pre-commit-hooks)
10. [CI/CD Pipeline & Quality Gates](#10-cicd-pipeline--quality-gates)
11. [Sandbox & Preview Environments](#11-sandbox--preview-environments)
12. [Security & Guardrails](#12-security--guardrails)
13. [Cost Envelope](#13-cost-envelope)
14. [Phased Delivery](#14-phased-delivery)
15. [Open Questions & Risks](#15-open-questions--risks)
16. [What Will Be Scaffolded Next (Pending Approval)](#16-what-will-be-scaffolded-next-pending-approval)

---

## 1. Goal & Decision Driven

**The decision this system serves**: _Reduce the human's role in software delivery to "Information Officer + Product Owner + final approver", while keeping every change legally/operationally defensible and within a lean budget._

The human (admin) does three things only:

1. **Submits** a bug or feature from inside the app.
2. **Validates** the agents' work in a sandbox (UAT) from inside the app.
3. **Approves** the production deploy (the single mandatory human gate).

Everything else — clarification, design, coding, review, security, testing, merging, staging — is performed by agents, gated by **non-bypassable automated checks**.

---

## 2. Confirmed Decisions

| #   | Decision                | Choice                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Agent runtime / harness | **Amazon Bedrock AgentCore — managed harness (preview)** in **Europe (Frankfurt) `eu-central-1`**. Each agent is declared as model + system prompt + tools; the harness runs the full reasoning→tool→action loop (no orchestration code), giving each session its **own microVM with filesystem + shell access**. Plus Gateway, Identity, Memory, Observability. **AWS Step Functions** coordinates the cross-agent SDLC graph + gates where deterministic control is needed |
| D2  | Repo topology           | **Monorepo** (recommended below)                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| D3  | Merge autonomy          | **Fully autonomous merge on green**; human approval required only for **production deploy**                                                                                                                                                                                                                                                                                                                                                                                  |
| D4  | Intake system of record | **GitHub Issues** (the app is a thin admin submit UI bridged to Issues)                                                                                                                                                                                                                                                                                                                                                                                                      |
| D5  | Sandbox / preview model | **On-demand ephemeral preview** (serverless, scale-to-zero) + the AgentCore **managed-harness microVM** (filesystem + shell) for build/test; **synthetic data only**                                                                                                                                                                                                                                                                                                         |
| D6  | Security tooling        | **OSS stack**: Semgrep (SAST), Trivy (containers/deps), gitleaks (secrets), tfsec/checkov (IaC)                                                                                                                                                                                                                                                                                                                                                                              |
| D7  | Dev-tooling budget      | **Lean: < $50/mo** (capped agent iterations, GitHub-hosted runner free tier, scale-to-zero infra)                                                                                                                                                                                                                                                                                                                                                                            |
| D8  | Documentation home      | **This companion doc** (keeps the product design focused)                                                                                                                                                                                                                                                                                                                                                                                                                    |

---

## 3. Key Tensions & Compensating Controls

### 3.1 Autonomous merge vs. the product's "human reviews everything" ethos

The product design (SOLUTION_DESIGN.md) gates **every substantive action** behind a human. For **code**, you have chosen autonomous merge on green. This is defensible — code is verifiable by deterministic tests in a way that legal correspondence is not — **but only if the gates are airtight**. Compensating controls:

- **Branch protection on `main`**: required status checks (all gates green), no force-push, linear history, signed commits, no direct pushes (PR-only, including from agents).
- **Security agent is a _required, blocking_ check** — a Critical/High finding fails the merge. Your hard "never" rules are encoded as gates that **cannot** be bypassed (no `--no-verify`, no skipping CI).
- **Eval harness gate** (product §14) is a required check — agents cannot merge a change that regresses grounding/citation accuracy.
- **Production deploy is human-gated** via a GitHub Environment protection rule (the admin is the required reviewer).
- **Kill switch**: a single repo variable / label (`automation:paused`) halts all agent automation immediately.
- **Iteration cap & token budget per issue** (budget + runaway-loop protection).

### 3.2 Lean budget vs. agentic iteration cost

Agentic coding loops can be token-expensive. Controls: AgentCore Runtime **scales to zero** (no idle cost); preview envs are **on-demand**, not per-push; eval/security run on PR (not every commit) with path filters; capped ret/iteration counts; Haiku-first triage, Sonnet for implementation, escalate sparingly.

### 3.3 Sandbox safety vs. realistic testing

Agent-built code must never touch production data, real Gmail, real Bedrock KB, or real money. Controls: a separate **`preview`/`sandbox` AWS account** (or strictly namespaced stack), **synthetic fixtures only**, mocked external services (LocalStack, mock Gmail/WhatsApp), and IAM that cannot reach prod resources.

---

## 4. Architecture Overview

```
                         ┌────────────────────────────────────────────┐
                         │   IN-APP DEV CONSOLE (admin role only)       │
                         │   submit bug/feature · watch · UAT · approve │
                         └───────────────┬──────────────────────────────┘
                                         │ (signed API call)
                                         ▼
                         ┌──────────────────────────────┐
                         │  Intake Bridge (Lambda)        │
                         │  → creates GitHub Issue         │
                         │  ← streams status back to app   │
                         └───────────────┬────────────────┘
                                         │ GitHub webhook
                                         ▼
        ┌────────────────────────────────────────────────────────────────────────┐
        │              SDLC ORCHESTRATOR (Step Functions + AgentCore)              │
        │                                                                          │
        │  Triage → Architect → Coder → (Reviewer ‖ Security ‖ Testing) → Release  │
        │            ▲                              │                              │
        │            └────────── iterate on failed gate / admin feedback ─────────┘│
        └───────────────┬───────────────────────────────────┬──────────────────────┘
                        │                                   │
              AgentCore harness · eu-central-1     GitHub Actions (CI gates)
              AgentCore Identity → GitHub App        lint · typecheck · unit ·
              Harness microVM (fs+shell sandbox)     integration · security ·
              AgentCore Memory (project context)      eval · build · deploy
                        │                                   │
                        ▼                                   ▼
              Ephemeral Preview Env (on-demand)      Production (human-gated)
              synthetic data only                    OIDC deploy, smoke + rollback
```

**Why AgentCore fits the constraints** (region: **Frankfurt `eu-central-1`**):

- **Managed harness (preview)** declares each agent as _model + system prompt + tools_ and runs the full agent loop (reasoning, tool selection, action, streaming) with **no orchestration code**; models are swappable mid-session and any create-time config is overridable per invocation → fast iteration, **scales to zero** → lean cost.
- **Per-session microVM** (filesystem + shell access) **is** the build/test sandbox — agents compile/run/test inside an isolated VM. **Filesystem persistence (preview)** lets an agent suspend mid-task and resume exactly where it left off.
- **Identity** brokers short-lived GitHub App tokens and AWS credentials → **no stored secrets/PATs** (honours the hard "never" rule).
- **Gateway** exposes GitHub/AWS/CI operations to agents as governed MCP tools.
- **Memory** persists project conventions and prior decisions (repo memory) across issues.
- **Observability** gives traces of every agent action → the SDLC audit trail.
- **Promotion path**: prototype on the harness, then export to **Strands-based** code for full control; deploy via the **AgentCore CLI** as IaC. _Caveat:_ the CLI supports \*_AWS CDK today; Terraform is "coming soon"_ — so AgentCore resources are managed via CDK/CLI while the rest of the AWS estate (SSM Parameter Store, IAM/OIDC, DynamoDB, etc.) stays in Terraform (§6, infra/).

---

## 5. Dev-Agent Roster

Mirrors the product's specialist pattern; the **Reviewer is deliberately separate from the Coder** to enforce the Layer-2 "internal critic" independently.

| #   | Agent                   | Responsibility                                                                                   | Key tools (via AgentCore Gateway)                   | Model        |
| --- | ----------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------- | ------------ |
| 1   | **Orchestrator**        | SDLC state machine, gating, retries, kill switch                                                 | Step Functions (not an LLM)                         | —            |
| 2   | **Triage / Planner**    | Read Issue, clarify acceptance criteria (may ask admin back in-app), label, decompose into tasks | `get_issue`, `comment_issue`, `label`, `ask_admin`  | Haiku        |
| 3   | **Architect**           | Approach for non-trivial work; respects existing patterns (repo Memory)                          | `read_repo`, `search_code`, `read_memory`           | Sonnet       |
| 4   | **Coder / Implementer** | Branch, implement, write tests, open PR                                                          | `git`, `write_files`, `open_pr`, `code_interpreter` | Sonnet       |
| 5   | **Reviewer**            | Independent code review on the PR; requests changes                                              | `get_pr_diff`, `review_pr`, `comment`               | Sonnet       |
| 6   | **Security**            | Run Semgrep/Trivy/gitleaks/tfsec; triage; **block on Critical/High**                             | `run_scanners`, `annotate_pr`                       | Haiku→Sonnet |
| 7   | **Testing / QA**        | Extend unit/integration/e2e; run product eval harness (§14); coverage gate                       | `run_tests`, `run_eval`, `coverage`                 | Sonnet       |
| 8   | **Release Manager**     | SemVer, changelog, deploy staging, prep prod for human approval, rollback                        | `tag`, `changelog`, `deploy`, `rollback`            | Haiku        |
| 9   | **Sandbox / Preview**   | Provision on-demand ephemeral env for UAT; tear down                                             | `provision_preview`, `destroy_preview`              | Haiku        |

---

## 6. Repository Topology (Recommendation)

**Recommendation: a single monorepo** — best practice for AI-native delivery because agents reason over one coherent tree, cross-cutting changes are atomic, and there is one CI/eval/tooling config to govern.

```
stak-platform/                      # monorepo
├── .github/
│   ├── workflows/                  # CI gates, deploy, preview, scheduled evals
│   ├── ISSUE_TEMPLATE/             # bug.yml, feature.yml (used by intake bridge)
│   └── CODEOWNERS                  # agents + human owner
├── infra/                          # Terraform/CDK (prod, staging, preview, sandbox)
├── services/                       # backend Lambdas (8 product agents, intake bridge)
├── frontend/                       # Next.js dashboard (incl. admin Dev Console)
├── sdlc-agents/                    # the 9 dev agents + Step Functions definitions
│   ├── orchestrator/
│   ├── triage/ architect/ coder/ reviewer/ security/ testing/ release/ preview/
│   └── shared/                     # AgentCore client, tool definitions, prompts/skills
├── eval/                           # golden-set eval harness (product §14)
├── tooling/                        # pre-commit config, scripts, generators
├── tests/                          # cross-cutting integration/e2e
├── .pre-commit-config.yaml
├── package.json / pyproject.toml   # workspaces
└── README.md
```

Rationale notes:

- The **SDLC agents live in the same repo they build** → they version with the code, and can self-improve their own prompts/skills under the same gates.
- A **second, tiny repo** is justified only for the **GitHub App** (the app manifest/credentials broker) if you want its lifecycle isolated; otherwise keep it in `infra/`.

---

## 7. End-to-End Workflow

```
1. Admin submits bug/feature in app (Dev Console)            ──► Intake Bridge ──► GitHub Issue (templated, labelled)
2. Webhook → Orchestrator starts SDLC run
3. Triage/Planner: writes acceptance criteria; if ambiguous → asks admin in-app (one round), else proceeds
4. Architect: approach + impacted areas (uses repo Memory for conventions)
5. Coder: feature branch, implementation + tests, opens PR (draft → ready)
6. CI gates run on PR:  lint → typecheck → unit → integration(LocalStack) → security → eval → build
   • Reviewer / Security / Testing agents post required reviews
   • On any failure → Coder iterates (capped N iterations / token budget)
7. ALL GREEN → auto-merge to main (squash, signed)            ◄── D3 autonomous merge
8. Release Manager: deploys main to STAGING; on admin request spins up EPHEMERAL PREVIEW (synthetic data)
9. Admin UAT in-app (Dev Console shows preview link + checks): APPROVE or FEEDBACK
   • FEEDBACK → new iteration (back to step 5)
10. APPROVE → Release Manager deploys to PRODUCTION via GitHub Environment (human-gated) + OIDC
11. Post-deploy smoke tests; auto-rollback on failure; Issue closed; full trace in Observability + audit
```

**Human touchpoints**: (a) optional one-round clarification at triage, (b) UAT approve/feedback, (c) production-deploy approval. Nothing else.

---

## 8. In-App Dev Console & Intake Bridge

A new **admin-only** area in the dashboard (RBAC: `CHAIRPERSON`/admin), separate from the trustee surfaces.

| Component        | Purpose                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Submit panel** | Bug or Feature form → maps to `.github/ISSUE_TEMPLATE` fields (title, description, steps/expected, priority, screenshots). Creates a GitHub Issue via the Intake Bridge. |
| **Work board**   | Live status of each Issue's SDLC run (Triage → … → Release), sourced from Step Functions + GitHub.                                                                       |
| **UAT panel**    | Preview-env link, automated-check summary, **Approve** / **Request changes** (free-text feedback → Issue comment → new iteration).                                       |
| **Deploy gate**  | Production-deploy **Approve** button (drives the GitHub Environment required-review).                                                                                    |
| **Audit view**   | Per-Issue trail: agent actions, gate results, diffs, deploy record.                                                                                                      |

**Bridge security**: the in-app submit calls an authenticated API (Cognito JWT, admin scope) → Lambda → GitHub App (short-lived token via AgentCore Identity). No PATs in the browser or server. Status streams back via the existing API Gateway WebSocket.

---

## 9. Pre-Commit Hooks

`pre-commit` framework, mirrored as CI required checks (defense-in-depth; hooks are **never** bypassable in CI even if skipped locally):

| Hook                        | Tool                                  | Blocks on                                         |
| --------------------------- | ------------------------------------- | ------------------------------------------------- |
| Secret scan                 | **gitleaks** + `detect-secrets`       | any detected secret (hard "never" rule)           |
| Python lint/format          | **ruff** + **black**                  | lint errors, format drift                         |
| Python types                | **mypy** (or pyright)                 | type errors                                       |
| JS/TS lint/format           | **eslint** + **prettier**             | lint errors, format drift                         |
| TS types                    | **tsc --noEmit**                      | type errors                                       |
| IaC                         | **terraform fmt** + **tfsec**/checkov | misconfig, format                                 |
| SAST (staged)               | **semgrep --error**                   | matched rules                                     |
| Commit message              | **commitlint** (Conventional Commits) | non-conforming messages (drives SemVer/changelog) |
| Large files / merge markers | pre-commit built-ins                  | accidental commits                                |

> Per your guardrails: hooks **must not** be disabled and CI re-runs every check, so a local `--no-verify` cannot land non-compliant code.

---

## 10. CI/CD Pipeline & Quality Gates

GitHub Actions, OIDC to AWS (no stored cloud creds). Required, blocking checks on `main`:

```
PR opened/updated
  ├─ lint + format        (ruff/black, eslint/prettier, tf fmt)
  ├─ typecheck            (mypy, tsc)
  ├─ unit                 (pytest, vitest)         coverage ≥ threshold
  ├─ integration          (LocalStack, SFN Local, mock Gmail/WhatsApp)
  ├─ security  [BLOCKING]  (semgrep, trivy, gitleaks, tfsec)  fail on Critical/High
  ├─ eval      [BLOCKING]  (product §14 golden-set: grounding 100%, fabricated-citation 0%)
  └─ build                (artifacts / container images)
        │ all green
        ▼
   AUTO-MERGE (squash, signed)  →  deploy STAGING
        │
        ▼
   on-demand PREVIEW (admin)  →  UAT approve  →  PRODUCTION (human-gated Environment) → smoke → rollback-on-fail
```

**Definition of "good" (pre-execution, per Layer 2)** reuses the product thresholds (§14.3) plus SDLC-specific gates: zero High/Critical security findings, coverage ≥ target on changed modules, all eval gates pass, conventional-commit compliance.

---

## 11. Sandbox & Preview Environments

Most cost-effective AI-native model under the lean budget:

- **Build/test sandbox** = the AgentCore **managed-harness microVM** (per session, filesystem + shell, no standing infra). Agents compile, run unit/integration tests, and iterate here; filesystem persistence allows suspend/resume of long tasks.
- **Integration** = **LocalStack** + Step Functions Local + mocked Gmail/WhatsApp in CI (no real AWS spend).
- **UAT preview** = **on-demand** ephemeral serverless stack (CDK/SAM) in a separate `preview` account, deployed only when the admin requests UAT, **auto-destroyed** on approve/reject or a TTL (e.g., 4h). Scales to zero → near-zero idle cost.
- **Data** = synthetic fixtures only. The preview env has **no path** to production DynamoDB/S3, real Gmail, real Bedrock KB, or WhatsApp.

---

## 12. Security & Guardrails

| Control                  | Implementation                                                                                        |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| No stored secrets        | AgentCore **Identity** issues short-lived GitHub App + AWS tokens; OIDC for deploys                   |
| Least privilege          | Scoped GitHub App permissions; per-agent IAM roles; preview account isolated from prod                |
| Branch protection        | `main`: PR-only, required checks, signed commits, linear history, no force-push                       |
| Blocking security gate   | Semgrep/Trivy/gitleaks/tfsec must pass; Critical/High fails merge                                     |
| Supply chain             | Pinned deps, Trivy SCA, Dependabot (optional), provenance on build artifacts                          |
| Prod gate                | GitHub Environment required reviewer = admin                                                          |
| Kill switch              | `automation:paused` repo variable/label halts the orchestrator                                        |
| Budget guardrails        | Iteration cap + per-issue token budget; alerts on overrun                                             |
| Audit                    | AgentCore Observability traces + GitHub history + deploy records = full SDLC trail                    |
| Prompt-injection defense | Treat Issue/PR/comment text as untrusted; tool allow-lists; no shell exec outside the harness microVM |

---

## 13. Cost Envelope

Target **< $50/mo** at low throughput (a handful of issues/week):

| Item                                | Approach                                                                     | Est.           |
| ----------------------------------- | ---------------------------------------------------------------------------- | -------------- |
| Agent inference (Bedrock)           | Haiku-first triage, Sonnet for code, capped iterations                       | ~$15–30        |
| AgentCore managed harness (microVM) | No charge for the harness/CLI/skills; pay underlying compute, scales to zero | ~$5–10         |
| GitHub Actions                      | GitHub-hosted free minutes (public/low usage)                                | $0             |
| Preview envs                        | On-demand serverless, auto-destroy, synthetic data                           | ~$2–5          |
| Storage/observability               | S3/CloudWatch low volume                                                     | ~$2            |
| **Total**                           |                                                                              | **~$25–47/mo** |

Throughput is the main cost driver; the iteration cap + on-demand preview keep it bounded.

### 13.1 Greenfield zero-baseline strategy

Starting from **no GitHub repo and no AWS account**, the spend ramp is deliberately lazy:

- **P0 = $0.** Gates, hooks, CI, and templates are **GitHub-only** on a Free **public** repo (unlimited Actions minutes). No AWS account is needed yet.
- **First dollar is Bedrock.** Bedrock has **no free tier** — every token is billed. Everything else we use (Lambda, DynamoDB, API Gateway, SQS, Cognito, Step Functions, CloudWatch) fits the **AWS Free Tier** at this volume. So AWS stays ~$0 until an agent actually runs (P1+).
- **Defer AgentCore + Bedrock** until P1 needs a live agent; the harness **scales to zero**, so idle cost is ~$0.
- **Free-by-default choices:** **SSM Parameter Store (SecureString)** for the GitHub App key instead of Secrets Manager (~$0.40/secret/mo saved); 2 free **AWS Budgets**; free **Cost Anomaly Detection**.
- **Day-one guardrails** (see `infra/cost-guardrails/` + the bootstrap checklist): a **zero-spend budget alert**, a small monthly cap, anomaly detection, free-tier usage alerts, and root-account MFA — set the moment the AWS account is created.

---

## 14. Phased Delivery

| Phase                     | Outcome                                                                                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0 — Foundations**      | Monorepo + pre-commit hooks + base CI gates (lint/type/unit/security) + branch protection + GitHub App via AgentCore Identity. _No agents yet — gates first._ |
| **P1 — Intake loop**      | Issue templates + in-app Dev Console submit + Intake Bridge + Triage agent (Issue → spec).                                                                    |
| **P2 — Build loop**       | Coder + Reviewer + Testing agents; PR automation; auto-merge on green.                                                                                        |
| **P3 — Release loop**     | Security agent as blocking gate; Release Manager; staging deploy; on-demand preview; UAT panel; human-gated prod deploy + rollback.                           |
| **P4 — Self-improvement** | Agents tune their own prompts/skills under the same gates; eval-gated skill mutation; metrics dashboard.                                                      |

> Gates and guardrails (P0) ship **before** any autonomous agent — so autonomy is never ungated.

---

## 15. Open Questions & Risks

| #   | Item                                       | Note                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OQ1 | AgentCore availability/region              | **Resolved.** The managed harness (preview) runs in **Europe (Frankfurt) `eu-central-1`** (one of four supported regions). The SDLC control-plane runs there and handles **code only, never POPIA data**; all product data + storage stays in **`af-south-1`**.                                                                                                                                                                                                                        |
| OQ2 | GitHub plan / repo visibility              | **Resolved.** GitHub **Free** + **public** repo. Per GitHub docs, rulesets/branch protection on Free are available on **public** repos only (private needs Pro/Team), and public repos get **unlimited Actions minutes** — so public is the only $0 path that still enforces the gated-autonomy model. Trade-off: source is visible; mitigated because the repo holds **zero secrets** (gitleaks/detect-secrets/semgrep gates) and all secrets + POPIA data live in AWS, never in Git. |
| OQ3 | "Fully autonomous merge" sign-off          | Confirm you accept agent-authored code merging to `main` without human review, relying solely on gates (mitigated by §3.1).                                                                                                                                                                                                                                                                                                                                                            |
| OQ4 | Single human approver                      | Production-deploy gate assumes one admin; add a backup reviewer to avoid a bottleneck.                                                                                                                                                                                                                                                                                                                                                                                                 |
| R1  | Runaway agent loops burn budget            | Iteration/token caps + alerts + kill switch.                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| R2  | Gate gaming (agent weakens a test to pass) | Reviewer + eval baseline + coverage-cannot-decrease rule + protected eval/test dirs in CODEOWNERS.                                                                                                                                                                                                                                                                                                                                                                                     |
| R3  | Prompt injection via Issue/PR text         | Untrusted-input handling, tool allow-lists, sandboxed exec only.                                                                                                                                                                                                                                                                                                                                                                                                                       |
| R4  | Preview env data leakage                   | Separate account, synthetic data, no prod IAM path.                                                                                                                                                                                                                                                                                                                                                                                                                                    |

---

## 16. What Will Be Scaffolded Next (Pending Approval)

On your go-ahead, **P0 first** (gates before agents):

1. Initialise the **monorepo** structure (§6) — empty workspaces + README.
2. Add **`.pre-commit-config.yaml`** (§9) and `tooling/` setup.
3. Add **base GitHub Actions** workflows (lint/type/unit/security) + **branch-protection** config + `CODEOWNERS` + Issue templates.
4. Stub the **AgentCore Identity / GitHub App** wiring (no secrets committed).

I will **not** create repositories, push, or enable automation until you approve this spec. Reply with any changes, or "proceed with P0" to begin scaffolding.

---

_End of Document_
