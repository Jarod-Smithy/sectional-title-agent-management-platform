# 0011. Frontend test stack

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The production frontend is a Next.js (App Router, TypeScript) app mirroring the
prototype across five trustee surfaces plus an admin Dev Console, with Cognito SRP
login. The `node` CI gate runs `npm run typecheck` + `npm test --if-present`, but a
greenfield frontend ships with no test scaffolding, so the gate is dormant. We need a
$0, hermetic frontend test stack that activates the `node` gate and can't drift from the
backend API contract.

## Decision

We will standardise on an all-$0 frontend test stack:

- **Vitest + `@testing-library/react`** for unit/component tests (jsdom env), with
  co-located `*.test.tsx`.
- **MSW** for API mocking, with handlers derived from the FastAPI OpenAPI schema.
- **Playwright** for e2e against `next start` + a local uvicorn `StubLLM` API with
  seeded SQLite, run in a **separate `frontend-e2e` job** so it doesn't slow the fast
  `node` path.
- **`@axe-core/playwright` + `vitest-axe`** for accessibility (zero serious/critical).
- **`openapi-typescript`** to generate client types from the API schema so `tsc` fails
  on contract drift.

E2E auth must **not** drive real Cognito SRP: run the API with `STAK_AUTH_ENABLED=false`
for happy-path e2e, or seed a token minted from the same RSA test keypair the backend
uses. A real SRP login stays an opt-in `@live` Playwright project.

## Consequences

### Positive

- Activates the `node` gate as a real safety net for agent-authored TS.
- Contract types keep the frontend from silently drifting from the API.
- Fully hermetic and $0.

### Negative / costs

- Playwright browser download adds CI time (cache it); the e2e job needs to boot both
  the API and the web server.

### Neutral / follow-ups

- ✅ Vitest + MSW unit/component tests landed with the frontend scaffold.
- ⬜ Playwright e2e + axe, `frontend-e2e` job, and `openapi-typescript` client are
  follow-ups.

## Alternatives considered

- **Jest instead of Vitest** — rejected: Vitest aligns with the Vite/ESM toolchain and
  is faster.
- **Cypress instead of Playwright** — rejected: Playwright's multi-server `webServer`
  config and free parallelism fit the seeded-API e2e model better.
- **Real Cognito in e2e** — rejected: costs/quotas and nondeterminism; injected JWKS is $0.
