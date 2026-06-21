# 0005. Lambda runs outside a VPC

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** platform engineering

## Context

A common default is to place Lambda inside a VPC for "network isolation". Our
backend talks only to **managed AWS services** — DynamoDB, Cognito, Bedrock
(cross-region), S3 — each reached over TLS and authorised by IAM. There are
**no network-reachable resources** (no RDS, no ElastiCache, no private hosts) to
isolate on a private subnet. Putting Lambda in a VPC with no internet egress
would also **break** the Cognito JWKS fetch and Bedrock calls unless we add
interface VPC endpoints or a NAT Gateway — both of which carry standing cost
that conflicts with the **$50 cap** ([ADR-0001](0001-aws-serverless-cost-cap.md)).

## Decision

We will run the API Lambda **outside any VPC**. The security boundary is
**IAM least-privilege + Cognito + TLS**, not network placement. Bedrock
permissions are attached only when explicitly enabled
([ADR-0006](0006-bedrock-direct-adapter.md)); DynamoDB access is scoped to the
table ARN.

## Consequences

### Positive

- No NAT Gateway (~$32/mo) or interface-endpoint charges — preserves the cap.
- No risk of breaking JWKS/Bedrock egress from a no-egress subnet.
- Simpler networking; faster cold starts (no ENI attachment).

### Negative / costs

- We forgo network-layer isolation; we rely entirely on IAM/TLS/Cognito, which
  must therefore be kept tight.

### Neutral / follow-ups

- If a future private data plane is required, the cheap win is a **DynamoDB
  gateway VPC endpoint (free)** — but Bedrock + Cognito JWKS would then need
  interface endpoints ($) or a NAT Gateway, to be weighed against the cap at
  that time.

## Alternatives considered

- **Lambda in a private VPC with NAT Gateway** — rejected: standing monthly cost
  blows the budget for no isolation benefit (no private resources exist).
- **Lambda in a VPC with interface endpoints for every service** — rejected:
  per-endpoint hourly cost; over-engineered for this workload.
