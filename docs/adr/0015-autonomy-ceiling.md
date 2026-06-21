# 0015. Autonomy ceiling

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner)

## Context

An AI-native SDLC can range from "every agent PR is human-merged" to "agents auto-merge
on green." We need to state how much autonomy we are willing to grant, and how it is
earned, so the question isn't re-litigated per PR. The constraints are a single human
owner (a review bottleneck) and a hard $50 lifetime cap.

## Decision

We will grant autonomy **graduated by tier, earned on measured eval pass-rate**, with a
firm ceiling:

- **Default:** every agent PR is **human-merged**. Agents propose via PR; they never
  push to `main`, never force-push, never `--no-verify`.
- **Tier 1 (earliest auto-merge candidate):** auto-merge limited to **docs/tests-only**
  changes that pass `All gates`, once the agent demonstrates a stable eval pass-rate and
  a clean provenance record. CODEOWNERS-protected paths are **never** auto-merged.
- **Product/infra changes** stay human-merged indefinitely; production deploy remains a
  human action (merge to `main` → `deploy.yml`).
- Any tier can be revoked instantly via the kill-switch (`automation:paused`).

## Consequences

### Positive

- A clear, auditable autonomy policy that can tighten or loosen deliberately.
- The highest-risk surfaces (product, infra, guardrails) keep a human in the loop.

### Negative / costs

- The single-owner review bottleneck remains; needs a backup approver / break-glass.

### Neutral / follow-ups

- Define the exact eval-pass-rate threshold and observation window for Tier 1.
- Revisit the ceiling once a backup approver exists and provenance gating is live
  ([ADR-0012](0012-agent-bot-identity-and-codeowner-enforcement.md)).

## Alternatives considered

- **No auto-merge ever** — viable and safest; kept as the default until Tier 1 is
  explicitly enabled.
- **Auto-merge product code on green** — rejected: gates are strong but not infallible;
  product/infra risk warrants a human.
