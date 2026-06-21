# 0012. Agent bot identity and code-owner enforcement

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

Branch protection requires code-owner review, but it **auto-waives that review for
owner-authored PRs**. Today the only identity is the human owner (`@Jarod-Smithy`). If
an SDLC agent authored PRs _as the owner_, every PR would auto-waive code-owner review —
the entire CODEOWNERS guardrail (the mechanism that keeps humans in the loop and stops
an agent weakening its own checks) would be void.

## Decision

We will require SDLC agents to act through a **distinct GitHub App / bot identity**, not
the human owner, so their PRs are **non-owner** PRs that **require** the human
code-owner's approval.

- The GitHub App has **least-privilege scopes**: contents, issues, pull-requests —
  **not** admin, **not** workflow-edit.
- The App private key lives in the AgentCore Identity token vault / SSM `SecureString`;
  the agent receives short-lived tokens and never sees the raw key.
- A future **agent-provenance gate** asserts the PR author is the bot identity, the
  branch is agent-prefixed, commits are gitsign-signed, and rejects any agent PR
  touching a CODEOWNERS-protected path (defence-in-depth beyond review).

## Consequences

### Positive

- Makes "humans stay in the loop" actually true rather than nominal.
- Clean audit separation between human-authored and agent-authored changes.

### Negative / costs

- One more identity to register, scope, and rotate.

### Neutral / follow-ups

- ⬜ Register the GitHub App, install it on the repo, store the key in SSM.
- ⬜ Add the agent-provenance gate.
- Revisit if GitHub later changes owner-auto-waive semantics.

## Alternatives considered

- **Agent uses the owner's PAT/identity** — rejected: bypasses code-owner review;
  structurally unsafe.
- **Drop owner auto-waive entirely (require review even for the human)** — rejected:
  blocks the solo owner on routine human PRs; a backup approver / break-glass is the
  better mitigation for the single-owner bottleneck.
