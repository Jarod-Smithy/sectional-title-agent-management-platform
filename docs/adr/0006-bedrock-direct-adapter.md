# 0006. Direct Bedrock Converse adapter for app-facing inference

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** platform engineering

## Context

The trustee-facing application needs real LLM inference for three jobs: drafting
email replies, answering grounded questions, and suggesting document metadata.
These are **synchronous, request-scoped** calls from the API Lambda, already
modelled behind an `LLM` port with a deterministic `StubLLM` for offline
dev/CI. Inference must run in the eu-west-1 inference plane
([ADR-0002](0002-two-region-data-inference-split.md)) and must stay **zero-cost
until deliberately switched on** under the $50 cap.

A managed agent runtime (AgentCore) is also coming for the SDLC/ops agents
([ADR-0007](0007-agentcore-harness-for-sdlc.md)), which raises the question of
whether app inference should go through that harness too.

## Decision

We will implement a **direct `BedrockLLM` adapter** against the Bedrock
**Converse API** that satisfies the existing `LLM` port, selected at runtime by
`STAK_LLM_PROVIDER` in the composition root. App-facing inference is a plain
Converse call — **not** routed through the AgentCore harness.

Safety and cost defaults:

- Provider default stays **`stub`** — no Bedrock calls until explicitly flipped.
- The Bedrock `InvokeModel` IAM policy is attached only when
  `bedrock_enabled = true` (Terraform default `false`) — **no standing
  permissions** otherwise, scoped to the eu Claude inference-profile/foundation
  -model ARNs (no bare `*`).
- Model tier is configurable (fast/balanced/deep → Haiku/Sonnet/Opus); the
  resolved model ID carries the region geo prefix.
- `answer_question` short-circuits with no model call when there is no grounding
  context; `suggest_metadata` falls back to stub heuristics on bad output.

## Consequences

### Positive

- Simple, synchronous, low-latency path for request-scoped inference.
- Zero standing spend and zero standing IAM until two explicit flags are set.
- Reuses the proven `LLM` port; `StubLLM` keeps dev/CI offline and free.

### Negative / costs

- App inference does not get the harness's managed memory/observability — by
  design; those belong to the agent runtime, not per-request app calls.

### Neutral / follow-ups

- Going live = grant Bedrock model access, set `bedrock_enabled = true` and
  `STAK_LLM_PROVIDER = bedrock`, deploy, validate one draft (spends against cap).

## Alternatives considered

- **Route app inference through the AgentCore harness** — rejected: heavyweight
  for synchronous request/response; couples the app to the agent runtime and its
  per-use billing for a job that is a single model call.
- **Third-party Anthropic API** — rejected: sends data to a public LLM API,
  violating the in-account / no-PII-to-public-API rule (Bedrock is in-account).
