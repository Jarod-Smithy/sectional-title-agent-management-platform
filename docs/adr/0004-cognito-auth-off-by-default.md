# 0004. Cognito JWT auth, off by default

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The platform is **trustees-only** — the Chairperson and a few trustees log in;
owners and tenants never do (they interact by email). We need authentication
that is free at this scale, supports RBAC, and keeps personal data access
controlled. At the same time, the auth surface is being built before any trustee
user or dashboard token flow exists, and we must not break the already-deployed
API or its passing test suite while wiring it.

## Decision

We will use **AWS Cognito** (invite-only user pool, admin-create-only, SPA
client with no secret, SRP) for human authentication, verifying **RS256 access
tokens** in the API via a `CognitoVerifier` (PyJWT `PyJWKClient`).

Enforcement is **off by default**, gated by `STAK_AUTH_ENABLED`
(Terraform `auth_enabled`, default `false`):

- **Off:** a synthetic dev principal is injected; all routes behave as before.
- **On:** every route except `/api/health` requires a valid Cognito **access**
  token; the verifier checks signature, issuer, expiry, `token_use == access`,
  and `client_id`, and **fails closed** (503) if enabled without a configured
  verifier.

Advanced Security and MFA stay off for now (cost / pre-user friction).

## Consequences

### Positive

- Auth is fully implemented and tested without disturbing the live API.
- Cognito free tier keeps cost at $0; flipping one flag activates enforcement.
- Fail-closed behaviour prevents an "enabled but unconfigured" open door.

### Negative / costs

- A real gap exists between "implemented" and "enforced" until a trustee user
  and dashboard token flow are in place.

### Neutral / follow-ups

- Activation trigger: a trustee user exists in the pool **and** the dashboard
  sends `Authorization: Bearer <access_token>`.
- TOTP (software-token) MFA preferred when MFA is enabled (free vs SMS).
- Cognito Advanced Security (the only paid feature) stays off unless a threat
  model requires it.

## Alternatives considered

- **Enforce auth immediately** — rejected: would break the deployed API and
  tests before any user/token flow exists.
- **Custom/self-managed JWT issuer** — rejected: more code and key custody for no
  benefit over Cognito's free tier.
