# 0001. AWS serverless (Lambda + DynamoDB) under a $50 cap

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

The platform serves a **single** sectional-title scheme run by volunteer
trustees, funded on a personal credit card with a hard **$50 total lifetime
cost cap** and a zero-spend goal while idle. Traffic is tiny and bursty (a
handful of trustee actions and inbound emails per day). The workload is a
FastAPI application plus document/RAG storage. POPIA requires the data to stay
in South Africa (`af-south-1`).

Any always-on compute (containers on ECS/Fargate, an RDS/Aurora Postgres
instance, a NAT Gateway) carries a standing monthly charge that would consume
the entire budget within weeks regardless of usage.

## Decision

We will run the backend as **AWS Lambda behind an HTTP API Gateway**, with
**DynamoDB** (single-table, on-demand) as the system of record and S3 for
documents. We will **not** use RDS/Aurora, always-on containers, or a NAT
Gateway. The FastAPI app is adapted into Lambda via Mangum. Local development
uses SQLite (see [ADR-0003](0003-pluggable-repository-port.md)).

## Consequences

### Positive

- Scales to zero — no standing compute cost; spend tracks actual usage.
- DynamoDB on-demand + Lambda + API Gateway all sit within free-tier limits at
  this volume, keeping us at ~$0/month.
- Fits the existing terragrunt/OIDC infra and the cost-guardrail budgets.

### Negative / costs

- Relational queries/joins are unavailable; data is modelled for single-table
  DynamoDB access patterns.
- Lambda cold starts add latency (acceptable for this workload).

### Neutral / follow-ups

- Postgres was explicitly dropped from the design.
- Point-in-time recovery and a customer-managed KMS key are deferred for cost
  (tracked in the deferred backlog).

## Alternatives considered

- **RDS/Aurora Postgres** — rejected: standing instance + storage cost blows the
  $50 cap even when idle.
- **ECS/Fargate containers** — rejected: always-on task cost; over-provisioned
  for the traffic.
- **DynamoDB provisioned capacity** — rejected: on-demand is cheaper and simpler
  at near-zero, bursty volume.
