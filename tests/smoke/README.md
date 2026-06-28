# STAK post-deploy smoke test

A standalone, **real-HTTP** smoke test that exercises the **live deployed** STAK
system (API Gateway → Lambda FastAPI + CloudFront). There is **no mocking** — every
assertion hits the actual deployed endpoints.

It exists to catch the class of bug where an API Gateway / Lambda **CORS preflight
returns HTTP 400 ("Disallowed CORS origin")**, which silently breaks every browser
call from the dashboard. Unit tests never catch this because it only manifests
against the real gateway configuration.

This package is intentionally isolated: it has its **own** `package.json` and does
**not** depend on the frontend build.

## Run locally

```bash
cd tests/smoke
npm install
npm run smoke
```

Against a different environment, override via env vars:

```bash
SMOKE_API_BASE=https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com \
SMOKE_ORIGIN=https://d2vcnwv2hywkdo.cloudfront.net \
npm run smoke
```

If your shell is behind a corporate proxy that blocks outbound HTTPS to AWS,
clear the proxy vars first:

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy proxy
```

Type-check only (no network):

```bash
npm run typecheck
```

## Configuration

| Env var                   | Default                                                   | Purpose                                 |
| ------------------------- | --------------------------------------------------------- | --------------------------------------- |
| `SMOKE_API_BASE`          | `https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com` | API Gateway base URL                    |
| `SMOKE_ORIGIN`            | `https://d2vcnwv2hywkdo.cloudfront.net`                   | Dashboard origin used in CORS preflight |
| `SMOKE_COGNITO_REGION`    | `af-south-1`                                              | Cognito region (optional auth path)     |
| `SMOKE_COGNITO_CLIENT_ID` | `1g4ori9ppoc432omgiu6s7efsa`                              | Cognito app client (optional auth path) |
| `SMOKE_USERNAME`          | _(unset)_                                                 | Enables the optional authenticated path |
| `SMOKE_PASSWORD`          | _(unset)_                                                 | Enables the optional authenticated path |

## What is mandatory vs optional

**Mandatory** (the run exits non-zero if any fail):

1. `GET {API}/api/health` → `200`, JSON `status === "ok"`.
2. CORS preflight regression — `OPTIONS /api/documents` (request method `GET`) →
   `2xx` **and** an `access-control-allow-origin` header equal to `*` or
   `SMOKE_ORIGIN`. Must **not** be `400`.
3. CORS preflight regression — `OPTIONS /api/documents/upload-url` (request method
   `POST`) → same assertion as above.
4. `GET {API}/api/documents` with **no** `Authorization` header → `401` (proves the
   route exists, the CORS layer passes, and auth is enforced).

**Optional** (runs only when `SMOKE_USERNAME` **and** `SMOKE_PASSWORD` are set;
otherwise **SKIPPED**, never fails):

5. Authenticated round-trip — Cognito `USER_PASSWORD_AUTH` login → `GET
/api/documents` (`200`) → `POST /api/documents/upload-url` (`200` + `uploadUrl`)
   → `PUT` a few bytes to the presigned S3 URL (`200`/`204`). If
   `USER_PASSWORD_AUTH` is not enabled on the app client, the auth error is caught
   and the check is **skipped gracefully**.

The test prints a `PASS` / `SKIP` / `FAIL` line per check plus a final summary.
