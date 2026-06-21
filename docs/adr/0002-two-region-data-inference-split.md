# 0002. Two-region split: data in af-south-1, inference in eu-west-1

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Chairperson (product owner), platform engineering

## Context

POPIA pushes us to keep the scheme's personal data (owners, units,
correspondence, financials) resident in South Africa, so the data plane lives in
**af-south-1**. However, **Amazon Bedrock is not available in af-south-1** — the
Claude models we need for drafting and Q&A are only reachable from other
regions. We need real LLM inference without moving the system of record out of
South Africa.

POPIA §72 permits cross-border processing where the destination offers adequate
protection; the EU qualifies. Inference requests carry only the minimal context
needed to answer, not the document store.

## Decision

We will operate **two regions**:

- **af-south-1 — data plane.** DynamoDB, S3, Lambda, Cognito, API Gateway. This
  is enforced by OPA policy (`policy/terraform.rego` denies any AWS provider
  region other than `af-south-1`).
- **eu-west-1 — inference plane.** Bedrock cross-region inference profiles for
  Claude, invoked on demand from the af-south-1 Lambda.

The inference region is configurable (`STAK_BEDROCK_INFERENCE_REGION`,
default `eu-west-1`) and the resolved model ID carries the matching geo prefix
(`eu.`), so the split is explicit in both settings and IAM scoping.

## Consequences

### Positive

- The system of record and all personal data stay in South Africa.
- We get Claude inference despite Bedrock's af-south-1 gap.
- The OPA region guard prevents accidental data-plane drift to another region.

### Negative / costs

- Cross-region calls add latency and a small data-transfer consideration.
- Two regions to reason about for IAM, observability, and ADR-0007 agent
  placement.

### Neutral / follow-ups

- Inference sends minimal prompt context only; the corpus is never shipped
  cross-region wholesale.
- The future AgentCore harness ([ADR-0007](0007-agentcore-harness-for-sdlc.md))
  must pick a GA region kept separate from the af-south-1 data plane.

## Alternatives considered

- **Single region (af-south-1 only), no Bedrock** — rejected: no managed Claude
  inference; would force a third-party API (violates the no-PII-to-public-LLM
  rule) or self-hosting (cost).
- **Move the whole stack to a Bedrock region** — rejected: breaks POPIA data
  residency for the system of record.
