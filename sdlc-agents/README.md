# sdlc-agents

The nine **dev agents** that build and maintain this repository
([docs/AI_NATIVE_SDLC_DESIGN.md §5](../docs/AI_NATIVE_SDLC_DESIGN.md)). They run on
Amazon Bedrock AgentCore (scale-to-zero) and are coordinated by a Step Functions graph.

| Folder          | Agent            | Role                                                              |
| --------------- | ---------------- | ----------------------------------------------------------------- |
| `orchestrator/` | Orchestrator     | SDLC state machine, gating, retries, kill switch (Step Functions) |
| `triage/`       | Triage / Planner | Issue → acceptance criteria, decompose, label                     |
| `architect/`    | Architect        | Approach for non-trivial work (uses repo Memory)                  |
| `coder/`        | Coder            | Branch, implement + tests, open PR                                |
| `reviewer/`     | Reviewer         | Independent code review (separate from Coder)                     |
| `security/`     | Security         | Semgrep/Trivy/gitleaks/tfsec; blocks on Critical/High             |
| `testing/`      | Testing/QA       | Unit/integration/e2e + eval harness; coverage gate                |
| `release/`      | Release Manager  | SemVer, changelog, staging deploy, prod prep, rollback            |
| `preview/`      | Sandbox/Preview  | On-demand ephemeral UAT env; tear down                            |
| `shared/`       | —                | AgentCore client, tool/Gateway definitions, prompts/skills        |

> Stubs only — agents arrive in SDLC Phases P1–P3, **after** P0 gates are live.
