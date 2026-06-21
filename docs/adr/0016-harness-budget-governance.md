# 0016. Harness budget governance

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner)

## Context

The AgentCore harness has no fixed fee but bills pay-per-use (Runtime vCPU/GB-hr,
Gateway, Memory, Bedrock model rates, CloudWatch). A disciplined loop costs roughly
**$0.45–$1.30 per PR** and **$6–$17/month** at ~3 PRs/week — a meaningful fraction of
the **$50 lifetime** cap ([ADR-0001](0001-aws-serverless-cost-cap.md)). Without an
enforced sub-budget and an automatic circuit-breaker, a runaway agent loop could consume
the cap.

## Decision

We will carve a **standing per-month harness sub-cap** (initially **$10**) out of the
$50 lifetime cap, enforced by a **cost circuit-breaker** that auto-trips the kill-switch
— not merely alerts.

- Reuse `infra/cost-guardrails/` (the `stak-zero-spend` and `stak-monthly-cap` budgets +
  anomaly detection already applied).
- Stack token/cost controls: invoke-only-on-demand (scale to zero); deterministic git
  ops (zero model tokens on plumbing); **Haiku for plumbing, Sonnet for Coder/Reviewer,
  never Opus** in the loop; per-session minute, per-issue iteration, and token caps.
- A budget-threshold breach **auto-trips** `automation:paused`, halting all agent
  activity until a human re-enables it.

## Consequences

### Positive

- The $50 lifetime cap is protected by construction, not vigilance.
- Cost is observable and bounded before any agent stands up.

### Negative / costs

- The breaker may pause legitimate work; re-enabling is a deliberate human action.

### Neutral / follow-ups

- ⬜ Wire the budget alarm → kill-switch automation (today it only alerts).
- Tune the $10 sub-cap as real per-PR cost is measured during the Planner PoC.

## Alternatives considered

- **Alert-only budgets (no auto-trip)** — rejected: an overnight runaway loop could
  spend the cap before a human reacts.
- **No sub-cap (rely on the $50 lifetime budget)** — rejected: gives no monthly
  guardrail and no early circuit-breaker.
