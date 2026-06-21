# 0009. Changed-line coverage 100% and coverage-cannot-decrease

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

During bootstrap, changed-line coverage was relaxed to `diff-cover --fail-under=90` to
unblock early scaffolding. Once agents author product code, a soft changed-line floor
lets unsafe or untested lines slip through one PR at a time. The diff-budget already
caps PRs at 50 files / 1500 lines, so 100% coverage of _changed_ lines is achievable
without blocking large refactors.

## Decision

We will require **100% coverage of changed Python lines** on every PR
(`diff-cover --fail-under=100`), and we will add a **coverage-cannot-decrease** ratchet
so total line-rate may not regress.

- Exemptions are **line-level `# pragma: no cover` only** — never file-level — and are
  reserved for defensive branches (e.g. JWKS-fetch failure) and real-AWS code behind
  the `live` marker.
- The coverage thresholds live in `pyproject.toml`, which is CODEOWNERS-protected.

## Consequences

### Positive

- Every new or modified line is exercised; agents cannot trade coverage for velocity.
- Pairs with mutation testing ([ADR-0010](0010-mutation-testing-on-safety-modules.md))
  to resist assertion-free "coverage theatre."

### Negative / costs

- Guard branches that can't be hit must be explicitly `# pragma: no cover` with a
  reason, adding small annotation overhead.

### Neutral / follow-ups

- ✅ `diff-cover --fail-under=100` restored (delivered).
- ⬜ Coverage-cannot-decrease ratchet (store baseline `coverage.xml` total, compare on
  PR) — not yet built.

## Alternatives considered

- **Keep `--fail-under=90`** — rejected: leaves a steady leak of untested changed lines.
- **Project-wide 100% floor** — rejected: punishes legitimate defensive code and
  third-party-shaped branches; changed-line 100 + pragma is the right granularity.
