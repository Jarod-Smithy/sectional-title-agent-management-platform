# tests

Cross-cutting integration and end-to-end tests ([docs/SOLUTION_DESIGN.md §14.1](../docs/SOLUTION_DESIGN.md)).
Per-package unit tests live next to their code under `services/`, `frontend/`, `sdlc-agents/`.

| Layer       | Tooling                                                     |
| ----------- | ----------------------------------------------------------- |
| Integration | LocalStack + Step Functions Local; mocked Gmail/WhatsApp    |
| Contract    | API ↔ dashboard schema snapshots; agent I/O JSON contracts |
| End-to-end  | Playwright against an ephemeral stack                       |

> Human-owned via CODEOWNERS so agents cannot weaken the safety net (R2).
