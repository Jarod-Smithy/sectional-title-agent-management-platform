# AI-Native Build Plan & Bootstrap Checklist

**Date:** 19 June 2026
**Companion to:** [VISION_AND_REQUIREMENTS.md](VISION_AND_REQUIREMENTS.md) (the _what_) and [AI_NATIVE_SDLC_DESIGN.md](AI_NATIVE_SDLC_DESIGN.md) (the existing factory design)
**Basis:** Opus 4.8 research review of the repo's existing SDLC design + 2025/2026 best practice.
**Principle:** **Gates before agents.** No autonomous agent runs against a repo that lacks the P0 guardrails below.

---

## 1. Summary of the delivery model

A "software factory" where specialised AI agents own **spec → code → review → security → test → release**, with the human as **Information Officer + Product Owner + final approver**. The human does three things: **submit** (feature/bug), **validate** (UAT in sandbox), **approve** (production deploy — the single mandatory gate).

The existing [AI_NATIVE_SDLC_DESIGN.md](AI_NATIVE_SDLC_DESIGN.md) is strong and already sequences gates-before-agents, an independent reviewer/critic, blocking security + eval gates, OIDC-only deploys, no stored secrets, a kill-switch, and iteration/budget caps. This plan **hardens the gaps** and re-scopes delivery to the leaner trustees-only MVP.

---

## 2. Gaps to close in the existing SDLC design

**Must-fix before enabling autonomous merge:**

- **G1 — Supply-chain integrity:** add **Syft** (SBOM), **cosign/Sigstore** (sign images + attestations), **SLSA** provenance; verify signatures at deploy. Sign commits with **gitsign**.
- **G4 — Policy-as-code:** add **OPA/Conftest** for org rules (region allow-list, no public S3, no wildcard IAM) on top of tfsec/Checkov.
- **G5 — Anti-gate-gaming tests:** **mutation testing** (mutmut/cosmic-ray for Python, StrykerJS for TS) on critical modules + **coverage-cannot-decrease** (`diff-cover`) as required checks.
- **G6 — Typed MCP tool permissioning:** per-agent tool **allow-lists**, typed/scoped tool contracts, **dry-run** mode.
- **G9 — Graduated autonomy:** replace binary auto-merge with **earned tiers** (below).
- **G12 — Diff-size budget:** cap files/lines changed per agent run for reliable eval/review.

**Important (P1–P3):**

- **G2 — DAST:** OWASP ZAP against the ephemeral preview env.
- **G3 — Dependency automation:** Renovate or Dependabot (gated).
- **G8 — Observability schema:** structured per-decision/tool-call events + trace-ID propagation Issue → SFN → PR → deploy.
- **G10 — Cost circuit-breaker:** auto-trip the kill-switch on budget threshold (not just alerts).
- **G7 — Backup approver / break-glass** for the single-approver bottleneck.

**Acknowledge/document:**

- **G11 — Public-repo dependency:** non-bypassable rulesets on GitHub Free require a public repo; document this trade-off.

---

## 3. Graduated ("earned") autonomy model

Maps directly to the product's per-intent autonomy requirement (Vision §4.10).

| Tier                  | SDLC behaviour                                                                                  | Product behaviour                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **0 — Shadow**        | Agent opens PR; human merges. Measure quality.                                                  | Agent drafts; human does everything.                                                              |
| **1 — Low-risk auto** | Auto-merge on green for docs/tests/copy only.                                                   | Auto-send **bare acknowledgements** only.                                                         |
| **2 — Bounded auto**  | Auto-merge app code under diff-size budget; infra/security/eval paths still human (CODEOWNERS). | Auto-handle low-risk intents that have passed **N = 3 approved runs** (no intervening rejection). |
| **3 — Full auto**     | Auto-merge on green; **prod still human-gated**.                                                | Broader auto intents; **no-gos (Vision §4.9) never automate**.                                    |

Promotion is driven by **measured eval pass-rate / escaped-defect rate**, not calendar time.

---

## 4. Ordered bootstrap checklist

### P0 — Foundations (gates before any agent; ~$0, GitHub-only)

1. Confirm repo scaffold; public Free repo (document G11 trade-off).
2. `.pre-commit-config.yaml`: gitleaks, detect-secrets, ruff/black, mypy, eslint/prettier, `tsc --noEmit`, terraform fmt, tfsec, Checkov, Semgrep, commitlint.
3. CI workflows (mirror hooks): lint → typecheck → unit → integration (LocalStack) → security (Semgrep/Trivy/gitleaks/tfsec/Checkov) → **Conftest policy** → build.
4. `eval/` golden-set + stored **regression baseline**; wire as a **required** check (used for SDLC agents; product agents use lighter manual spot-checks per Vision §4.11).
5. Coverage gate (`diff-cover`, cannot-decrease) + **mutation testing** on critical modules.
6. **CODEOWNERS** protecting `.github/`, `eval/`, `tests/`, `infra/`, `.pre-commit-config.yaml`.
7. **Ruleset/branch protection** on `main`: PR-only, all required checks, **signed commits (gitsign)**, linear history, no force-push, **include administrators**.
8. Issue templates (`bug.yml`, `feature.yml`) + **Renovate/Dependabot**.
9. Build job: **Syft SBOM** + **cosign** signing + **SLSA** provenance; verify at deploy.

### P0.5 — AWS safety (do FIRST in AWS, ~$0)

10. Create AWS account, **root MFA**, stop using root; Identity Center admin.
11. Cost guardrails: zero-spend Budget + monthly cap + **Cost Anomaly Detection** + free-tier alerts.
12. **GitHub OIDC → short-lived deploy roles** (no stored creds); per-env least-privilege.
13. GitHub App auth via SSM Parameter Store (SecureString); **no PATs**.

### P1 — Intake loop

14. Dev Console **submit** + Intake Bridge Lambda + GitHub Issue creation + **Triage/Spec agent** (Haiku, capped).
15. **Observability schema + trace-ID propagation** in place **before** the first agent runs.

### P2 — Build loop

16. **Coder + independent Reviewer + Testing** agents; PR automation.
17. **Tier 0/1 auto-merge only** (low-risk paths) under diff-size budget.
18. **Typed MCP tool allow-lists** per agent (Triage can't write code; Coder can't deploy).

### P3 — Release loop

19. **Security agent** as blocking gate; **DAST (ZAP)** on preview.
20. **Release Manager**; staging deploy (plan-gated); on-demand preview env (synthetic data, TTL auto-destroy).
21. UAT panel; **human-gated prod deploy** (GitHub Environments + required reviewer + OIDC); smoke + auto-rollback.
22. **Cost circuit-breaker** live (auto-trips kill-switch).

### P4 — Graduated autonomy & self-improvement

23. Promote merge autonomy **tier-by-tier** on measured metrics.
24. Eval-gated **skill mutation** (agents tune their own prompts/skills under the same gates).
25. Metrics dashboard; **backup approver / break-glass**.

### P0 implementation status (19 June 2026)

**Done in-repo (code/config landed):**

- ✅ #1–#2 Repo scaffold + `.pre-commit-config.yaml` (hygiene, gitleaks, detect-secrets, ruff, mypy, prettier, terraform_fmt, semgrep, commitlint).
- ✅ #3 CI gates in [.github/workflows/ci.yml](../.github/workflows/ci.yml) — lint/secrets/SAST, types, unit, **security** (gitleaks/semgrep/Trivy/Checkov), **Conftest policy** (G4, `policy/`), and the `All gates` aggregator.
- ✅ #5 Coverage-cannot-decrease via **diff-cover** (`--fail-under=100` on changed lines) + **mutmut** config in `pyproject.toml` (G5).
- ✅ #6 [.github/CODEOWNERS](../.github/CODEOWNERS) guards `.github/`, `eval/`, `tests/`, `infra/`, pre-commit config.
- ✅ #7 [.github/branch-protection.json](../.github/branch-protection.json) + `tooling/apply-branch-protection.sh`; **signed commits** via `tooling/enable-signed-commits.sh` (gitsign, G1).
- ✅ #8 Issue templates + **Dependabot** ([.github/dependabot.yml](../.github/dependabot.yml), actions/npm/pip/terraform).
- ✅ #9 **SBOM + signing + provenance** in [.github/workflows/supply-chain.yml](../.github/workflows/supply-chain.yml) — Syft SPDX SBOM + Grype scan always; cosign keyless sign + SLSA attestation guarded until the first image (P2).
- ✅ G12 **Diff-size budget** gate (`tooling/check-diff-budget.sh`, 50 files / 1500 lines, `oversized-change-approved` override).
- ◑ #4 Eval golden-set — `eval/` skeleton present; the blocking harness (`eval/run_eval.py`) arrives in P2/P3.

**Pending (human/AWS account actions — P0.5, require your console access):**

- ☐ #10 AWS account + root MFA + Identity Center admin.
- ☐ #11 Cost guardrails (zero-spend Budget, Cost Anomaly Detection) — Terraform in `infra/cost-guardrails/` to be applied.
- ☐ #12 GitHub OIDC → short-lived deploy roles (no stored creds).
- ☐ #13 GitHub App auth via SSM SecureString — `infra/github-app/` to be applied.

> **Next:** run `bash tooling/setup.sh` to install hooks locally, then apply branch protection + signed commits with the two `tooling/` scripts once the GitHub repo exists. Then P0.5 AWS setup, then P1 intake loop.

---

## 5. Product build sequence (rides on the SDLC factory)

Once P0–P1 foundations exist, the **first product increment** is the MVP triad (Vision §6), built by the factory:

1. **Document brain** — S3 + Bedrock Knowledge Base (authoritative corpus) **and** the Interaction Store (correspondence ledger), both agentic-RAG-queryable. _(Foundational — everything else grounds on it.)_
2. **Inbound email → grounded draft → approve/send → auto-file + ticket** — Gmail ingestion → classify → draft (concise, warm, natural) → human approval (except bare acknowledgements) → file to case/unit + create ticket.
3. **Trustee task board + issue-tracker** — Kanban, AI auto-ticketing from email, tickets linked to case/unit/document/resolution.

**Cross-cutting guardrails wired from day one:** resolution-gate hard-block, conflict self-declaration prompt, no-gos enforcement, defamation advisory screen, global kill-switch, per-intent autonomy tiers.

**Post-MVP phase:** financial oversight (Reserve/Admin health, scenario planning, 10-year maintenance planning, reserve-fund PMR-24 guard), then WhatsApp notifications.

---

## 6. Toolchain reference

| Concern             | Tools                                                                     |
| ------------------- | ------------------------------------------------------------------------- |
| Secrets             | gitleaks, detect-secrets, GitHub push-protection                          |
| SAST                | Semgrep (+ CodeQL optional)                                               |
| SCA / deps          | Trivy / Grype; Renovate / Dependabot                                      |
| IaC                 | terraform fmt, tfsec, Checkov, **OPA/Conftest**                           |
| DAST                | OWASP ZAP (preview env)                                                   |
| SBOM / signing      | Syft, cosign/Sigstore, SLSA provenance, gitsign                           |
| Coverage / mutation | diff-cover, mutmut/cosmic-ray (Py), StrykerJS (TS)                        |
| Orchestration       | AWS Step Functions (task tokens for HITL), EventBridge, SQS               |
| CI plane            | GitHub Actions (OIDC, no stored creds)                                    |
| Runtime             | Lambda + Fargate, Bedrock (Claude, Haiku-first), Cognito                  |
| Cost                | AWS Budgets, Cost Anomaly Detection, prompt caching, per-issue token caps |
