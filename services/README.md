# services

Backend Lambdas for the **product** (not the SDLC agents). Each product agent from
[docs/SOLUTION_DESIGN.md §7](../docs/SOLUTION_DESIGN.md) is a Lambda with a specialised
system prompt, tool definitions, and Bedrock Knowledge Base access.

Planned packages (created in product Phases 1–2):

| Package            | Role                                                                         |
| ------------------ | ---------------------------------------------------------------------------- |
| `email-ingestion/` | Gmail → SQS → parse → classify                                               |
| `orchestrator/`    | Step Functions task handlers                                                 |
| `agents/`          | Classifier, Legal, Financial, Compliance, Draft, Wilds, Maintenance, Copilot |
| `intake-bridge/`   | In-app Dev Console submit → GitHub Issue (SDLC §8)                           |
| `notification/`    | SES + WhatsApp                                                               |

> Empty for now — P0 establishes gates before code. Add packages as workspaces under
> `services/*` (see root `package.json` / `pyproject.toml`).
