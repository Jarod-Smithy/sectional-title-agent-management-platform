# 0014. Minimal SDLC agent roster (3, not 9)

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

`sdlc-agents/README.md` and the design doc list **nine** planned SDLC agents
(Orchestrator, Triage/Planner, Architect, Coder, Reviewer, Security, Testing, Release,
Preview). Standing up nine reasoning agents multiplies token spend against the $50
lifetime cap and operational surface — yet the **deterministic gates already do most of
the enforcement work** (Semgrep/Trivy/Checkov/pytest/diff-cover/SBOM/policy/deploy).

## Decision

We will start with a **minimal three-agent SDLC set**, and keep Security / Testing /
Release as **deterministic gates, not LLM agents**:

1. **Planner** (Haiku) — reads an Issue + repo Memory, posts acceptance criteria as a
   comment, labels/decomposes. Read-only on code; no write tools.
2. **Coder** (Sonnet) — implements + writes tests + runs gates locally in the microVM,
   then deterministic git push + draft PR. "Backend/frontend" personas are system-prompt
   - path-scope variations, **not** separate runtimes.
3. **Reviewer** (Sonnet) — a **separate session** from the Coder so the independent
   critic is real; posts a PR review. The only structurally-required second agent.

We promote Security/Testing/Release to LLM agents **only if** triage of gate output
becomes a measured bottleneck.

## Consequences

### Positive

- Minimises token spend and operational surface under the $50 cap.
- Keeps the safety net deterministic and human-owned.
- A separate Reviewer session gives a genuine second opinion.

### Negative / costs

- Fewer specialised agents means richer system prompts and path-scoping on the Coder.

### Neutral / follow-ups

- Roster size is reviewed as autonomy graduates ([ADR-0015](0015-autonomy-ceiling.md)).
- Architect/Orchestrator capabilities fold into Planner + the harness, not new agents.

## Alternatives considered

- **Stand up all nine agents** — rejected: cost and complexity with little marginal
  safety, since gates enforce most invariants.
- **A single do-everything agent** — rejected: loses the independent-critic property;
  Coder and Reviewer must be separate sessions.
