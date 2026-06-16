# Greenfield Bootstrap Checklist

Zero to a running, **cost-safe** AI-native SDLC — starting from **no GitHub repo and
no AWS account**. Do the steps in order. Spend stays at **$0** through Stage 3; the
**first dollar is Bedrock** (Stage 5).

> Design context: [docs/AI_NATIVE_SDLC_DESIGN.md](AI_NATIVE_SDLC_DESIGN.md) §13.1 (cost),
> §15 OQ2 (why a public repo), §12 (auth without secrets).

---

## Stage 0 — Decisions (done)

- [x] Runtime: **AWS Bedrock AgentCore** managed harness (preview), **eu-central-1** (Frankfurt) — code only.
- [x] Product data region: **af-south-1** (POPIA).
- [x] GitHub: **Free** plan, **public** repo (only $0 path that enforces required-check gates).
- [x] Secrets: **SSM Parameter Store** (SecureString, free), not Secrets Manager.

## Stage 1 — GitHub repo ($0)

- [ ] Create a **public** repo (Free plan) under your personal account.
- [ ] `git init`, commit the P0 scaffold, push to `main`.
- [ ] Replace `@OWNER` in [.github/CODEOWNERS](../.github/CODEOWNERS) with your GitHub handle.
- [ ] Settings → Actions → ensure Actions are enabled (public repos = **unlimited** free minutes).

## Stage 2 — Enforce the gates ($0)

- [ ] Open a throwaway PR; confirm the **`All gates`** check runs and is **required**.
- [ ] Apply branch protection: `tooling/apply-branch-protection.sh` (uses [.github/branch-protection.json](../.github/branch-protection.json)).
- [ ] Verify: a failing check **blocks merge**, and CODEOWNER review is required for guardrail paths.
- [ ] Install local hooks: `tooling/setup.sh` (pre-commit + secret scanners).

> Until Stage 2 passes, **do not** wire any autonomous merge — the gates are the safety net.

## Stage 3 — AWS account + cost guardrails ($0, do FIRST in AWS)

- [ ] Create the AWS account; set a strong root password + **MFA on root**.
- [ ] Stop using root: create an admin IAM user / Identity Center user for daily work.
- [ ] Billing console → **enable free-tier usage alerts** and **receive billing emails**.
- [ ] Apply [infra/cost-guardrails](../infra/cost-guardrails/README.md):
      `terraform apply -var="notification_email=you@example.com"` (zero-spend budget + monthly cap + anomaly detection — all free).
- [ ] Confirm the budget-alert verification email from AWS.

## Stage 4 — GitHub App auth, no secrets (~$0)

- [ ] Register a GitHub App (Settings → Developer settings → GitHub Apps → New).
      Permissions: contents, pull requests, issues, checks, actions (read/write as needed).
- [ ] Note the **App ID** and **Installation ID** (install the App on the repo first).
- [ ] Generate the App **private key** (.pem). Store it **free** in Parameter Store:
      `aws ssm put-parameter --name /stak/sdlc/github-app/private-key --type SecureString --value file://app-key.pem --region eu-central-1`
- [ ] Fill `infra/github-app/terraform.tfvars` (git-ignored) from the example; **no secret values** in tfvars.
- [ ] Delete the local `.pem` after upload.

## Stage 5 — First agent (first real cost: Bedrock)

> Defer until you actually want P1. Bedrock has **no free tier** — every token is billed.

- [ ] Confirm the **zero-spend budget** is active (Stage 3) before any Bedrock call.
- [ ] Stand up the AgentCore Identity workload via the **AgentCore CLI/CDK** (eu-central-1).
- [ ] Triage agent: **Haiku-first**, hard **iteration/token caps** (R1), kill switch.
- [ ] Everything else (Lambda, DynamoDB, API Gateway, SQS, Step Functions) stays within **AWS Free Tier**.

---

## Cost tripwires (review monthly)

| Signal                   | Likely cause                            | Action                                              |
| ------------------------ | --------------------------------------- | --------------------------------------------------- |
| Zero-spend budget fires  | Left the free tier                      | Find the service in Cost Explorer; confirm intended |
| Anomaly alert            | Runaway agent loop / unexpected service | Check iteration caps (R1); kill the session         |
| Actions minutes warning  | Repo went private, or heavy CI          | Keep repo public; trim workflow matrix              |
| Bedrock line item climbs | Too many/too-large model calls          | Lower iteration cap; Haiku for more steps           |
