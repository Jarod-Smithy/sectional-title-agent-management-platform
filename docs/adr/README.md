# Architecture Decision Records

This directory holds the **Architecture Decision Records (ADRs)** for the
Sectional Title Trustee Platform. An ADR captures a single significant
architectural decision: the context that forced it, the choice made, and the
consequences that follow.

We use a lightweight [MADR](https://adr.github.io/madr/)-style format. ADRs are
**immutable once accepted** — to change a decision, write a new ADR that
`Supersedes` the old one and flip the old one's status to `Superseded by`.

## Why we keep ADRs

The platform is built incrementally under a hard **$50 total cost cap**, so most
decisions are trade-offs between capability and spend (or between residency and
service availability). Recording them keeps the "why" durable as the codebase,
the team, and the AI-native SDLC agents evolve — and stops us re-litigating
settled questions.

## Index

| ADR                                                          | Title                                                        | Status   |
| ------------------------------------------------------------ | ------------------------------------------------------------ | -------- |
| [0000](0000-record-architecture-decisions.md)                | Record architecture decisions                                | Accepted |
| [0001](0001-aws-serverless-cost-cap.md)                      | AWS serverless (Lambda + DynamoDB) under a $50 cap           | Accepted |
| [0002](0002-two-region-data-inference-split.md)              | Two-region split: data in af-south-1, inference in eu-west-1 | Accepted |
| [0003](0003-pluggable-repository-port.md)                    | Pluggable repository port: SQLite local, DynamoDB in prod    | Accepted |
| [0004](0004-cognito-auth-off-by-default.md)                  | Cognito JWT auth, off by default                             | Accepted |
| [0005](0005-no-vpc-for-lambda.md)                            | Lambda runs outside a VPC                                    | Accepted |
| [0006](0006-bedrock-direct-adapter.md)                       | Direct Bedrock Converse adapter for app-facing inference     | Accepted |
| [0007](0007-agentcore-harness-for-sdlc.md)                   | AgentCore managed harness for the SDLC/ops agents            | Accepted |
| [0008](0008-agent-eval-gate-contract.md)                     | Agent Eval Gate contract (golden-set thresholds)             | Accepted |
| [0009](0009-changed-line-coverage-and-no-decrease.md)        | Changed-line coverage 100% and coverage-cannot-decrease      | Accepted |
| [0010](0010-mutation-testing-on-safety-modules.md)           | Mutation testing on safety-critical modules                  | Proposed |
| [0011](0011-frontend-test-stack.md)                          | Frontend test stack (Vitest/MSW/Playwright/axe)              | Accepted |
| [0012](0012-agent-bot-identity-and-codeowner-enforcement.md) | Agent bot identity and code-owner enforcement                | Proposed |
| [0013](0013-confirm-harness-region.md)                       | Confirm AgentCore harness GA region                          | Proposed |
| [0014](0014-minimal-sdlc-agent-roster.md)                    | Minimal SDLC agent roster (3, not 9)                         | Proposed |
| [0015](0015-autonomy-ceiling.md)                             | Autonomy ceiling (graduated autonomy)                        | Proposed |
| [0016](0016-harness-budget-governance.md)                    | Harness budget governance (sub-cap of $50)                   | Proposed |

## Creating a new ADR

1. Copy [`template.md`](template.md) to `NNNN-short-title.md` (next number, zero-padded).
2. Fill in Context, Decision, Consequences, and Alternatives.
3. Add a row to the index above.
4. Open a PR — ADRs are reviewed like code.
