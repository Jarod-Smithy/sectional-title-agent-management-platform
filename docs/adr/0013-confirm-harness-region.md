# 0013. Confirm AgentCore harness GA region

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

[ADR-0007](0007-agentcore-harness-for-sdlc.md) adopts the AgentCore managed harness for
SDLC agents and notes the GA region is **not af-south-1**. The older design doc
[AI_NATIVE_SDLC_DESIGN.md](../AI_NATIVE_SDLC_DESIGN.md) still fixes the harness at
**eu-central-1** (Frankfurt) — a stale value. We need a single authoritative region
that co-locates with the inference plane and stays clearly separate from the af-south-1
POPIA data plane ([ADR-0002](0002-two-region-data-inference-split.md)).

## Decision

We will host the harness in **eu-west-1** (matching the inference plane in
[ADR-0006](0006-bedrock-direct-adapter.md)), **subject to confirming managed-harness GA
availability there**. If the managed harness is not GA in eu-west-1, fall back to the
nearest GA region (e.g. us-west-2), keeping it **out of af-south-1**. The stale
eu-central-1 reference in the design doc is superseded by this ADR.

The microVM handles **code only, never POPIA data** — there is no path to the live
af-south-1 DynamoDB table; only synthetic fixtures are used.

## Consequences

### Positive

- One authoritative region; ends the design-doc vs ADR conflict.
- Co-location with inference; clean separation from the POPIA data plane.

### Negative / costs

- Cross-region latency between the eu-west-1 harness and any af-south-1 read is
  irrelevant because the harness never touches the data plane.

### Neutral / follow-ups

- ⬜ Verify managed-harness GA in eu-west-1 before `CreateHarness`; record the confirmed
  region here and revise the design doc.
- The harness is CDK-managed, not Terraform — the `policy/terraform.rego` af-south-1
  region guard governs only the data-plane HCL, so there is no policy conflict.

## Alternatives considered

- **eu-central-1 (per the stale design doc)** — rejected: not the inference region;
  inconsistent with ADR-0006/0007.
- **af-south-1** — rejected: not GA there, and would blur the POPIA data-plane boundary.
