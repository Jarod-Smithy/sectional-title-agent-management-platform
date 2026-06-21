# frontend

Production web dashboard for the Acacia Heights sectional-title trustee platform.
Next.js (App Router) + TypeScript + React, authenticated against Amazon Cognito
(SRP) and talking to the FastAPI backend in [`services/api`](../services/api).

UX contract: [docs/SOLUTION_DESIGN.md §13](../docs/SOLUTION_DESIGN.md) (wireframes §13.11).
The admin-only **Dev Console** ([docs/AI_NATIVE_SDLC_DESIGN.md §8](../docs/AI_NATIVE_SDLC_DESIGN.md))
for SDLC runs / UAT / production-deploy approvals is planned and not yet implemented.

## Surfaces

The dashboard exposes the five trustee surfaces backed by the API contract in
[`services/api/app/routes.py`](../services/api/app/routes.py):

| Tab           | Purpose                                                           |
| ------------- | ----------------------------------------------------------------- |
| `Inbox`       | Triage incoming owner/chair email into guardrailed draft actions. |
| `Board`       | Kanban of tickets (to do / in progress / done).                   |
| `Resolutions` | Filed and auto-filed resolutions.                                 |
| `Ask`         | Grounded Q&A over conduct rules with cited sources.               |
| `Documents`   | Document register + analysis.                                     |

## Local development

```bash
# from the repo root (installs all workspaces)
npm install

# copy env defaults and point at your API + Cognito pool
cp frontend/.env.example frontend/.env.local

cd frontend
npm run dev          # http://localhost:3000
```

Environment variables (see [`.env.example`](.env.example)):

| Variable                        | Description                         |
| ------------------------------- | ----------------------------------- |
| `NEXT_PUBLIC_API_BASE`          | Base URL of the FastAPI backend.    |
| `NEXT_PUBLIC_COGNITO_REGION`    | Cognito user-pool region.           |
| `NEXT_PUBLIC_COGNITO_POOL_ID`   | Cognito user-pool ID.               |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | Cognito app-client ID (public SPA). |

All client config is `NEXT_PUBLIC_*` (public values only — no secrets in the
browser bundle). Authentication uses the SRP flow via
`amazon-cognito-identity-js`; the access token is held in memory and attached as
`Authorization: Bearer <token>` on protected API calls.

## Quality gates

```bash
npm run typecheck    # tsc --noEmit
npm test             # vitest run (unit + integration, MSW-mocked API)
npm run test:e2e     # playwright (requires a production build: npm run build && npm start)
npm run build        # next production build
```

`typecheck` and `test` are wired into the root workspace scripts and run in the
CI **node** gate. The Playwright e2e smoke suite (`e2e/`) is intentionally **not**
part of the default CI gate and is run on demand against a local production build.

## Layout

```
src/
  app/            App Router pages (login, auth-gated dashboard) + providers
  components/     AppShell, status chips, and the five tab surfaces
  lib/            typed API client, Cognito auth context, config, hooks, types
  test/msw/       MSW handlers + server used by Vitest
e2e/              Playwright smoke + accessibility specs
```

`src/lib/types.ts` mirrors the backend Pydantic schemas in
[`services/api/app/schemas.py`](../services/api/app/schemas.py) one-to-one; keep
them in sync when the API contract changes.
