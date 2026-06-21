# 0007. AgentCore managed harness for the SDLC/ops agents

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The product vision is an **AI-native SDLC**: agents that run backend, frontend,
ops, security, CI/CD, and feature work once the foundations are in place. That
needs a runtime that can hold tools, identity/credentials, memory, and
observability for long-running agent sessions — distinct from the app's own
per-request inference ([ADR-0006](0006-bedrock-direct-adapter.md)).

Amazon **Bedrock AgentCore** reached GA on 18 June 2026 and offers a **managed
harness**: a thin abstraction over AgentCore primitives behind two API calls
(`CreateHarness` / `InvokeHarness`), powered by open-source **Strands** with
`agentcore export harness` as an escape hatch (no lock-in). The harness bundles
Identity (token vault), Memory, Gateway (tool auth), Browser, Code Interpreter,
Observability, Evals, and immutable versioning/rollback. A separate "adopt
AgentCore Identity?" question collapses into this — the harness provides Identity
automatically.

## Decision

We will adopt the **AgentCore managed harness** as the runtime for our SDLC/ops
agents (not for app-facing inference). The "coding agent" recipe maps to our
SDLC: push a repo+toolchain container to ECR → `CreateHarness` with a Gateway
target wired to GitHub → the agent reads code, plans, writes, runs tests, and
opens PRs, using `InvokeAgentRuntimeCommand` for **deterministic git ops**
(clone/commit/push/PR) so no model tokens are burned on plumbing. Outbound tool
credentials (GitHub/AWS/Jira) live in the Identity token vault; the agent never
sees raw secrets.

**We will not stand the harness up yet** — we keep the deterministic CI gates
and the app solid first, and only run a tiny cost-controlled PoC within the cap.

## Consequences

### Positive

- A managed, observable, credential-safe runtime for the AI-native SDLC.
- Identity comes bundled — no separate adoption decision.
- Strands export keeps an escape hatch; no hard lock-in.
- Complements Cognito: Cognito = human trustees; harness Identity = agent/tool
  creds, able to federate Cognito for on-behalf-of flows.

### Negative / costs

- No harness fee, but **pay-per-use underneath** (runtime vCPU/GB-hr, Gateway,
  Memory, model inference, observability) — real spend against the **$50 cap**,
  hence deferral.
- Another control plane to operate and secure.

### Neutral / follow-ups

- **Region:** GA is region-limited and **not af-south-1** — must verify the GA
  region, preferring eu-west-1 to match the inference plane, kept **separate from
  the af-south-1 POPIA data plane** (reinforces [ADR-0002](0002-two-region-data-inference-split.md)).
- Trigger to stand up the PoC: deterministic gates + app stable, with cost
  controls in place.
- Orthogonal to [ADR-0006](0006-bedrock-direct-adapter.md): the harness is for
  SDLC agents; app inference stays a direct Bedrock call.

## Alternatives considered

- **Build our own agent runtime** (orchestration, tool auth, memory,
  observability) — rejected: large undertaking; reinvents managed primitives.
- **Adopt AgentCore Identity standalone** — rejected/subsumed: the harness
  bundles Identity, so a separate adoption is redundant.
- **Run app inference through the harness too** — rejected: see
  [ADR-0006](0006-bedrock-direct-adapter.md); wrong tool for synchronous
  per-request calls.
