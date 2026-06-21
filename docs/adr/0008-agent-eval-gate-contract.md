# 0008. Agent Eval Gate contract

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The product's core safety property is **grounded, citation-backed answers** — it must
not fabricate sources, must cite the documents it relies on, and must reproduce dates
and rule versions verbatim. The CI `eval` job (the "Agent Eval Gate") was a no-op: it
only ran if `eval/run_eval.py` existed, so it passed trivially. This is the single most
important safety net before any agent authors product code, and it was hollow.

The gate must run at **$0** — no AWS, no paid tokens — to respect the $50 lifetime cap
([ADR-0001](0001-aws-serverless-cost-cap.md)).

## Decision

We will make the Agent Eval Gate **real and blocking**, asserting against the
deterministic `StubLLM` and the product's BM25 retriever over a versioned golden set.

- `eval/run_eval.py` imports the **same domain code the product uses** (`app.domain.rag`,
  `app.adapters.stub_llm.StubLLM`) — we evaluate the real brain, not a mock of it.
- `eval/golden/*.json` holds golden cases (documents + questions + expected sources +
  expected facts + answerability).
- Three thresholds are **blocking** (`--ci` exits non-zero on breach):
  **grounded-citation 100% / fabricated-citation 0% / date-version 100%**.
- The harness is covered by its own pytest (`eval/test_run_eval.py`) so the eval code
  itself satisfies the changed-line coverage gate ([ADR-0009](0009-changed-line-coverage-and-no-decrease.md)).
- `/eval/` stays **CODEOWNERS-protected** so an agent cannot soften thresholds.

## Consequences

### Positive

- The most dangerous false-green gate becomes a true safety net; a change that breaks
  grounding cannot merge.
- Prerequisite for ever trusting agent-authored PRs is satisfied.
- Fully deterministic and $0.

### Negative / costs

- The golden set must be curated and kept in sync with seed/fixture data.
- New domain behaviour needs matching golden cases or the gate gives false confidence.

### Neutral / follow-ups

- Share the golden set with the AgentCore harness eval primitive when the harness
  stands up, so CI and the harness agree.
- Add a single source of synthetic truth shared with integration fixtures.

## Alternatives considered

- **Keep the no-op gate** — rejected: it provided false assurance.
- **Evaluate a real Bedrock model in CI** — rejected: costs tokens, nondeterministic,
  breaches the $0 default-CI rule.
- **A separate mock brain for eval** — rejected: it would test the mock, not the product.
