# AI-Native SDLC — Operating Model

> How an AI-native SDLC should work for this repo, within the **$50 lifetime cost
> cap**. Folded from a research-and-ideation report. Where this document and the
> older [AI_NATIVE_SDLC_DESIGN.md](AI_NATIVE_SDLC_DESIGN.md) disagree (region, roster
> size, self-built vs managed orchestration), **[ADR-0007](adr/0007-agentcore-harness-for-sdlc.md)
> and the ADRs below are authoritative** and the design doc needs a revision pass.

Companion to [TESTING_STRATEGY.md](TESTING_STRATEGY.md). Decisions and open questions
here are captured as ADRs [0008–0016](adr/README.md).

## 1. Current state

### 1.1 What exists

**Deterministic gates (P0) — landed and battle-tested.** `.github/workflows/ci.yml`
defines jobs feeding a single aggregate required check `All gates`:

| Job (gate)    | Blocking?                                | Notes                                                                  |
| ------------- | ---------------------------------------- | ---------------------------------------------------------------------- |
| `lint-format` | yes                                      | ruff, mypy, prettier, gitleaks, detect-secrets, semgrep, terraform_fmt |
| `commitlint`  | yes on PR                                | drives SemVer/changelog                                                |
| `python`      | yes (when Python present)                | mypy strict + pytest + diff-cover `--fail-under=100`                   |
| `node`        | yes (when TS present)                    | tsc + unit                                                             |
| `security`    | yes — **Checkov still `soft_fail:true`** | gitleaks, Semgrep, Trivy vuln+secret                                   |
| `policy`      | yes                                      | Conftest/OPA; rego unit tests now present                              |
| `diff-budget` | yes on PR                                | 50 files / 1500 lines, `oversized-change-approved` override            |
| `eval`        | **yes (now real)**                       | golden-set grounding gate — see ADR-0008                               |

Plus `supply-chain.yml` (Syft SBOM + Grype, cosign sign + SLSA provenance) and
`deploy.yml` (OIDC role assume, Lambda code+layer update only, `/api/health` smoke).

**Guardrails.** `.github/CODEOWNERS` human-owns `/.github/`, `/.pre-commit-config.yaml`,
`/eval/`, `/policy/`, `/services/**/tests/`, `/infra/`, `/CODEOWNERS`, and product
code — all `@Jarod-Smithy` today. `policy/terraform.rego` enforces af-south-1-only
region, no public S3, no wildcard IAM, SSM `SecureString`. `tooling/check-diff-budget.sh`
implements the diff budget.

**Branch protection.** Required check = `All gates`; strict/up-to-date + linear
history (squash only); `enforce_admins=true`; code-owner reviews required;
dismiss-stale. **Owner-authored PRs auto-waive the code-owner review** — see §6 for
why this forces a distinct agent identity.

**Decisions captured.** ADRs 0000–0007; this document adds 0008–0016.

### 1.2 Gaps to a working AI-native SDLC

- **No SDLC agents yet.** `sdlc-agents/` is a README listing nine planned folders —
  "Stubs only." No harness, Gateway, Identity vault, ECR image, or agent code.
- **Bootstrap relaxations still open:** Checkov `soft_fail:true`, Trivy IaC misconfig
  off. (Eval gate, diff-cover 100, mutmut config, CODEOWNERS holes — now closed.)
- **No agent identity.** Everything is one human, so "owner auto-waives code-owner
  review" means an agent acting _as the owner_ would bypass review — a structural risk.
- **Stale design doc** (eu-central-1, 9 self-built agents) vs ADR-0007 (managed
  harness, deferred, eu-west-1 preferred).

## 2. Target operating model (end-to-end loop)

```
Tracked GitHub Issue (templated, label: agent:eligible, scoped path)
   ▼
[Plan agent]  reads issue + repo Memory → posts acceptance criteria as a comment
   │  human (Chairperson) 👍 the plan          ← lightweight gate #1
   ▼
[Coding agent]  in harness microVM: branch off origin/main → implement + tests
   │  runs gates LOCALLY first (pre-commit, pytest+cov, diff-budget, conftest verify)
   ▼
Deterministic git op (InvokeAgentRuntimeCommand): commit (gitsign) + push + draft PR
   ▼
CI fires: All gates + Supply Chain            ← the real safety net, non-bypassable
   │  red → agent iterates (capped iterations / token budget); green → mark ready
   ▼
Human review (Chairperson)                    ← gate #2, MANDATORY for protected paths
   │  squash-merge (linear history; strict = branch must be up-to-date)
   ▼
main → deploy.yml → OIDC → Lambda code+layer update → /api/health smoke
```

**Humans stay in the loop via CODEOWNERS, not trust.** Any PR touching a protected
path (`/.github/`, `/.pre-commit-config.yaml`, `/eval/`, `/policy/`, `/infra/`,
`/services/**/tests/`, `/CODEOWNERS`) requires the human code owner.

**Critical structural fix:** because owner-authored PRs auto-waive code-owner review,
the agent must **NOT** author PRs as the owner. It must use a **distinct GitHub App /
bot identity** so its PRs are _non-owner_ PRs that _do_ require human code-owner
approval. Otherwise the CODEOWNERS guardrail is moot. See [ADR-0012](adr/0012-agent-bot-identity-and-codeowner-enforcement.md).

## 3. Agent roster — two distinct planes

Keep two agent populations firmly apart:

**(a) Product runtime agents — the build _target_, not builders.** The 7-agent MVP
that runs _inside the trustee app_ (Orchestrator, Intake Classifier, Draft Composer,
Records Clerk, Ticketing Agent, Governance Guardian, Trustee Copilot). Lambdas in
af-south-1 using the direct BedrockLLM adapter ([ADR-0006](adr/0006-bedrock-direct-adapter.md))
in eu-west-1. They are _what the SDLC builds_.

**(b) Build-time SDLC/ops agents — the software factory.** Run in the AgentCore
harness ([ADR-0007](adr/0007-agentcore-harness-for-sdlc.md)), author code, open PRs.
They are _who builds_.

**Minimal SDLC set to start (3, not 9)** — see [ADR-0014](adr/0014-minimal-sdlc-agent-roster.md):

1. **Planner** (Haiku) — reads an Issue + repo Memory, writes acceptance criteria as a
   comment, labels/decomposes. Read-only on code; no write tools.
2. **Coder** (Sonnet) — implements + writes tests + runs gates locally in the microVM,
   then deterministic git push + draft PR. Its "backend/frontend" personas are just
   system-prompt + path-scope variations, not separate runtimes.
3. **Reviewer** (Sonnet) — _separate session from Coder_ so the independent critic is
   real; posts a PR review. The only structurally-required second agent.

Security / Testing / Release "agents" are **initially the deterministic gates
themselves** (Semgrep/Trivy/Checkov/pytest/diff-cover/SBOM + `deploy.yml`), not LLM
agents. Promote to LLM only if triage of gate output becomes a bottleneck.

## 4. AgentCore harness wiring (per ADR-0007)

1. **Container → ECR.** Build an `sdlc-agents/` toolchain image (Python 3.12,
   ruff/mypy/pytest, node, conftest, gitsign, the repo `tooling/` scripts). Push to ECR
   **in the harness region** (not af-south-1 — keep it off the POPIA data plane per
   [ADR-0002](adr/0002-two-region-data-inference-split.md)).
2. **`CreateHarness`** with the ECR image as `environmentArtifact`, a **Gateway target
   wired to GitHub** (governed MCP tools: `get_issue`, `comment_issue`, `get_pr_diff`,
   `review_pr`), `awsSkills` off initially.
3. **Identity token vault** — GitHub App private key + scoped AWS role; agent receives
   short-lived tokens, never raw secrets.
4. **Deterministic git ops** via `InvokeAgentRuntimeCommand` — clone/branch/commit
   (gitsign-signed)/push/PR run as shell commands, **not model tokens** (biggest cost
   lever).
5. **Memory** — seed with repo conventions: hexagonal ports/adapters, `STAK_*` env
   prefix, "provider defaults to stub", the af-south-1/eu-west-1 split, diff-budget
   limits, "never touch CODEOWNERS-protected paths."
6. **Observability** — CloudWatch GenAI traces give the audit trail (Issue → session →
   PR → deploy).
7. **Evals** — wire the harness eval primitive so it agrees with the CI Agent Eval Gate.

**Region:** GA is **not af-south-1**. The design doc's eu-central-1 is stale; ADR-0007
prefers eu-west-1 to co-locate with inference and stay separate from the af-south-1
POPIA data plane. Confirm GA availability — see [ADR-0013](adr/0013-confirm-harness-region.md).

**Smallest viable PoC:** one harness, **Planner only**, Gateway scoped to read Issues +
post one comment, triggered manually on a single labelled issue. Proves Identity +
Gateway + Memory + Observability + the cost meter for a few cents before any write
capability.

## 5. Mapping agents to the deterministic gates

_Gates are the safety net, not trust._ Every agent output is validated by existing
checks so an agent literally cannot merge an unsafe change.

| Agent action                          | Gate(s) that validate it                                                 |
| ------------------------------------- | ------------------------------------------------------------------------ |
| Coder writes Python                   | `python` (mypy strict, pytest, diff-cover 100)                           |
| Coder writes TS                       | `node` (tsc, unit)                                                       |
| Any code/secret                       | `lint-format` (ruff/mypy/gitleaks/detect-secrets/semgrep)                |
| Vulnerable dep / SAST / leaked secret | `security` + `supply-chain` (Syft/Grype)                                 |
| Touches Terraform                     | `policy` (Conftest: region, no public S3, no wildcard IAM, SecureString) |
| Over-large change                     | `diff-budget` (50 files / 1500 lines)                                    |
| Non-conventional commit               | `commitlint`                                                             |
| Weakening its own tests/eval/checks   | **CODEOWNERS** human review                                              |
| Regressing grounding/citation quality | **`eval` (Agent Eval Gate)**                                             |

**New gates worth considering (future):** an **agent-provenance gate** (assert PR
author is the bot identity, branch is agent-prefixed, commits are gitsign-signed,
reject if an agent PR touches a protected path); a **coverage-cannot-decrease**
ratchet ([ADR-0009](adr/0009-changed-line-coverage-and-no-decrease.md)).

## 6. Identity, security & guardrails

- **Credential model:** no raw secrets to the agent. GitHub App private key + scoped
  AWS role live in the Identity vault; the agent gets short-lived tokens. OIDC for any
  AWS deploy. SSM `SecureString` (rego-enforced) for the App key at rest.
- **Distinct agent identity (critical):** the agent acts as a **GitHub App / bot**, not
  the owner, so its PRs require human code-owner approval. See ADR-0012.
- **Least privilege:** scoped GitHub App permissions (contents, issues, pull-requests
  — _not_ admin, _not_ workflow-edit); per-agent AWS role that **cannot reach the
  af-south-1 data plane**. Preview/build uses synthetic data only.
- **Composition with Cognito ([ADR-0004](adr/0004-cognito-auth-off-by-default.md)):**
  Cognito = human trustees; harness Identity = agent/tool creds. Orthogonal planes.
- **OPA region guard:** `policy/terraform.rego` forces af-south-1 for the _data-plane_
  Terraform; the harness lives in eu-west-1 but is **not** Terraform-managed (CDK), so
  no conflict — documented so a future agent doesn't "fix" a perceived region violation.
- **Operational-safety rules (harness system-prompt + provenance gate):** agents
  **propose via PR, never push to main, never force-push, never `--no-verify`, never
  touch CODEOWNERS-protected paths.** Treat Issue/PR/comment text as **untrusted**
  (prompt-injection defence; tool allow-lists; shell only inside the microVM).

## 7. Cost model within the $50 cap

AgentCore has no harness fee but bills pay-per-use underneath (Runtime vCPU/GB-hr,
Gateway per-1k, Memory per-1k, Bedrock model rates, CloudWatch).

**Controls (stack them all):** invoke-only-on-demand (scale to zero); deterministic git
ops (zero model tokens on plumbing); Haiku for plumbing, Sonnet only for Coder/Reviewer,
**never Opus** in the loop; session-minute + iteration + per-issue token caps;
kill-switch (`automation:paused`); budget alarms wired to **auto-trip** the kill-switch
(reuse `infra/cost-guardrails/`).

**Rough per-PR envelope (Haiku plan + Sonnet code/review, deterministic git):**
≈ **$0.45–$1.30 per PR**, dominated by Sonnet coding tokens. At ~3 PRs/week ≈ **$6–17/mo**
if disciplined. Because $50 is a _lifetime_ cap, even one month of moderate use is a
meaningful fraction — hence ADR-0007's deferral and a standing per-month sub-cap
([ADR-0016](adr/0016-harness-budget-governance.md)). GitHub Actions stays $0 (public
repo, unlimited minutes).

## 8. Phased rollout

| Phase                       | Scope                                                                                                                                     | Exit criteria                                                                | Cost           |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------- |
| **P0 (done)**               | Deterministic gates, CODEOWNERS, branch protection, supply-chain, ADRs                                                                    | `All gates` green on real PRs                                                | $0             |
| **P0.5 (in progress)**      | Make the net real: eval gate ✅, CODEOWNERS holes ✅, diff-cover 100 ✅; remaining: Checkov `soft_fail:false`, Trivy IaC, blocking mutmut | net actually blocks; relaxations closed                                      | $0             |
| **P1 — read/plan agent**    | Single Planner (Haiku); Gateway read Issues + post one comment                                                                            | plan comment on 3 issues; cost < $0.10/issue                                 | ~cents         |
| **P2 — coding agent**       | Add Coder as bot identity; draft PRs on a narrow allow-listed path; deterministic git                                                     | 1 agent PR passes `All gates` + human-merged; never touched a protected path | ~$0.50–1.30/PR |
| **P3 — multi-agent**        | Add Reviewer (separate session); richer Gateway; kill-switch + cost circuit-breaker live                                                  | Reviewer catches a seeded defect; breaker trips on budget                    | ~$1–2/PR       |
| **P4 — graduated autonomy** | Earn merge-autonomy tier-by-tier on measured eval pass-rate                                                                               | Tier-1 auto-merge on docs/tests only; prod still human                       | variable       |

> Hard rule throughout: **gates before agents** — no phase grants autonomy the
> deterministic checks can't catch.

## 9. Open decisions → ADRs

The report surfaced decisions now captured as ADRs:

| ADR                                                              | Decision                                         | Status                                |
| ---------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------- |
| [0008](adr/0008-agent-eval-gate-contract.md)                     | Agent Eval Gate contract (golden-set thresholds) | Accepted (implemented)                |
| [0009](adr/0009-changed-line-coverage-and-no-decrease.md)        | Changed-line coverage 100 + cannot-decrease      | Accepted (diff-cover 100 done)        |
| [0010](adr/0010-mutation-testing-on-safety-modules.md)           | Mutation testing on safety modules               | Proposed (config done; job deferred)  |
| [0011](adr/0011-frontend-test-stack.md)                          | Frontend test stack                              | Accepted (partial; Vitest+MSW landed) |
| [0012](adr/0012-agent-bot-identity-and-codeowner-enforcement.md) | Agent bot identity & code-owner enforcement      | Proposed                              |
| [0013](adr/0013-confirm-harness-region.md)                       | Confirm AgentCore harness GA region              | Proposed                              |
| [0014](adr/0014-minimal-sdlc-agent-roster.md)                    | Minimal SDLC agent roster (3, not 9)             | Proposed                              |
| [0015](adr/0015-autonomy-ceiling.md)                             | Autonomy ceiling (graduated autonomy)            | Proposed                              |
| [0016](adr/0016-harness-budget-governance.md)                    | Harness budget governance (sub-cap of $50)       | Proposed                              |

## 10. Recommended immediate next step

The single missing piece of the safety net — the **Agent Eval Gate** — is now real and
blocking (ADR-0008). The next no-agent hardening moves are: re-tighten the bootstrap
relaxations (Checkov `soft_fail:false`, Trivy IaC misconfig) after a baseline IaC triage,
and decide the **agent bot identity** (ADR-0012) so the code-owner-review guardrail is
genuinely enforced. After that, the few-cent **Planner-only PoC** (§4) is the safe first
agent.
