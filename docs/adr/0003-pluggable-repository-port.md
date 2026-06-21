# 0003. Pluggable repository port: SQLite local, DynamoDB in prod

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** platform engineering

## Context

The domain logic was first proven in a zero-dependency stdlib prototype backed
by SQLite. Productionising onto DynamoDB ([ADR-0001](0001-aws-serverless-cost-cap.md))
must not require rewriting or re-validating that domain logic, and local
development/CI must stay fast and free (no AWS calls, no network, no
credentials). The corporate proxy also makes cloud dependencies during local
dev unreliable.

## Decision

We will define a `Repository` **port** (Protocol) and provide two **adapters**
behind it, selected at runtime by `STAK_REPO_BACKEND` via the composition root
(`app/bootstrap.py:build_repo`):

- **`sqlite`** (default) — local/dev/CI, embedded schema, zero dependencies.
- **`dynamodb`** — production, a single-table layout (pk/sk, no GSI) matching the
  `infra/modules/dynamodb` module; atomic counters via `UpdateItem ADD`,
  zero-padded sort keys for lexical ordering, cascade deletes without a GSI.

Domain code depends only on the port, never on a concrete store.

## Consequences

### Positive

- The same domain logic runs identically on SQLite and DynamoDB; tests stay
  offline and fast (DynamoDB adapter covered with `moto`).
- Production storage cost stays in DynamoDB free tier.
- Swapping or adding a backend is an adapter change, not a domain change.

### Negative / costs

- Single-table-no-GSI access patterns are more constrained; some lookups are
  modelled deliberately (title lookup, newest-first) rather than via ad-hoc
  queries.

### Neutral / follow-ups

- Default stays `sqlite` so nothing hits AWS unless explicitly configured.

## Alternatives considered

- **DynamoDB Local for dev** — rejected: heavier to run, needs Docker/JVM; SQLite
  is already proven and dependency-free.
- **One store everywhere (DynamoDB only)** — rejected: slow/credential-bound
  local loop, fragile behind the proxy.
