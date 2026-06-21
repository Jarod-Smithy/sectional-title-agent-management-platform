# 0000. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The platform is being productionised in small, individually-reviewed increments
under a hard **$50 total lifetime cost cap**. Almost every increment trades
capability against spend or against data-residency constraints (POPIA), and an
AI-native SDLC — where coding/ops agents will later make and act on changes —
amplifies the need for durable, machine-readable rationale. Decisions made in
chat or commit messages are easily lost; we keep re-litigating settled
questions.

## Decision

We will record every significant architectural decision as a numbered
Architecture Decision Record (ADR) in `docs/adr/`, using a lightweight
MADR-style format (Context / Decision / Consequences / Alternatives). ADRs are
immutable once accepted; a decision is changed only by a new ADR that supersedes
the old one. ADRs are reviewed in pull requests like code.

## Consequences

### Positive

- A durable, reviewable trail of "why" survives team and codebase churn.
- SDLC agents can read ADRs as authoritative context for the design.
- Cost/residency trade-offs are explicit and auditable.

### Negative / costs

- Small per-decision authoring overhead.

### Neutral / follow-ups

- Backfill ADRs 0001–0007 for decisions already made before this log existed.
- Link future increments to the ADR(s) they implement or supersede.

## Alternatives considered

- **Capture decisions only in commit messages / PR descriptions** — rejected:
  not discoverable, no single index, hard for agents to consume.
- **A single growing design doc** — rejected: large diffs, merge contention, and
  no clear immutability/supersession model.
