# 0010. Mutation testing on safety-critical modules

- **Status:** Proposed
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

Coverage and changed-line gates ([ADR-0009](0009-changed-line-coverage-and-no-decrease.md))
prove lines _run_, not that assertions _catch regressions_. An agent could write
assertion-free tests that inflate coverage while silently weakening a safety rule.
Mutation testing is the anti-gate-gaming net.

The repo had `[tool.mutmut]` configured but pointed at the empty top-level `tests/`
placeholder (`tests_dir = "tests/"`), so it found no tests and never ran; there was no
mutation CI job at all.

## Decision

We will run **mutmut** against the **safety-critical modules only** — `domain/guardrails.py`,
`domain/intake.py`, `security/cognito.py` — with the config pointed at the real test
suite (`tests_dir = "services/api/tests/"`). Surviving mutants in these modules
represent an un-caught behaviour change and must eventually fail CI.

The blocking CI job is **deferred** until we measure its runtime and Actions-minute
cost; mutation runs are slow and flaky for per-PR use. We will prefer a **scheduled**
(nightly) run over per-PR if the per-PR cost is material.

## Consequences

### Positive

- ✅ The config is fixed and scoped, so `mutmut run` works locally today.
- Stops "coverage theatre" on exactly the modules that encode go/no-go safety rules.

### Negative / costs

- Mutation runs are slow; per-PR blocking could lengthen the critical path. Hence the
  deferral and the scheduled-run preference.

### Neutral / follow-ups

- ⬜ Add a `mutation` CI job (scoped, scheduled or on-touch) that fails on surviving
  mutants in the safety modules.
- Expand the module set only after the runtime budget is understood.

## Alternatives considered

- **Per-PR blocking mutation on the whole codebase** — rejected: too slow/flaky, burns
  Actions minutes, would block the fast path.
- **No mutation testing** — rejected: leaves coverage gameable on safety code.
