# Sectional Title AI Agent Platform

Autonomous agentic property-management platform for a Sectional Title body corporate
(The Wilds Estate, Pretoria). This repository is **AI-native**: a team of specialised
agents owns the full software development lifecycle — spec → code → review → security →
test → release — with a human approving only at the production-deploy boundary.

> **Status:** P0 — Foundations (gates before agents). The CI gates, pre-commit hooks,
> and branch protection ship **before** any autonomous agent, so autonomy is never ungated.

## Documentation

| Doc                                                            | Purpose                                                           |
| -------------------------------------------------------------- | ----------------------------------------------------------------- |
| [docs/SOLUTION_DESIGN.md](docs/SOLUTION_DESIGN.md)             | Product architecture, agents, data, security, cost, UX            |
| [docs/AI_NATIVE_SDLC_DESIGN.md](docs/AI_NATIVE_SDLC_DESIGN.md) | The self-developing software factory (this repo's delivery model) |

## Monorepo Layout

```
sectional-title-agent-platform/
├── .github/            # CI gates, issue templates, CODEOWNERS, branch protection
├── docs/               # Design specs
├── infra/              # Terraform/CDK (prod, staging, preview, sandbox) + GitHub App
├── services/           # Backend Lambdas (8 product agents, intake bridge)
├── frontend/           # Next.js dashboard (incl. admin Dev Console)
├── sdlc-agents/        # The 9 dev agents + Step Functions orchestration
├── eval/               # Golden-set eval harness (product §14)
├── tests/              # Cross-cutting integration/e2e
├── tooling/            # Pre-commit, scripts, generators
├── .pre-commit-config.yaml
├── pyproject.toml      # Python workspace tool config
└── package.json        # JS/TS workspace + commit lint
```

## Quick Start (developers & agents)

```bash
# one-time
bash tooling/setup.sh        # installs pre-commit and the git hooks

# the hooks (and CI) enforce, non-bypassably:
#   secrets scan · lint/format · typecheck · IaC scan · SAST · conventional commits
```

## Hard Guardrails (non-negotiable)

- **No secrets in code.** gitleaks + detect-secrets block commits and CI.
- **No bypassing checks.** `--no-verify` cannot land non-compliant code; CI re-runs every gate.
- **No merge without green.** Security + eval/test gates are required, blocking checks on `main`.
- **Human gate at production deploy only** (GitHub Environment required reviewer).

See [docs/AI_NATIVE_SDLC_DESIGN.md §12](docs/AI_NATIVE_SDLC_DESIGN.md) for the full guardrail set.
