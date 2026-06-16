# infra

Infrastructure-as-code (Terraform) for all environments. Data residency is
**af-south-1** for product data (POPIA); the SDLC control-plane runs the AgentCore
**managed harness in Frankfurt (`eu-central-1`)**, handling **code only, never POPIA
data** (OQ1).

> AgentCore-specific resources are deployed via the **AgentCore CLI / AWS CDK** (Terraform
> support is "coming soon"); the rest of the AWS estate (SSM Parameter Store, IAM/OIDC,
> DynamoDB, S3, Step Functions) is Terraform.

> **Greenfield?** Apply `cost-guardrails/` **first** (free) and follow
> [docs/GREENFIELD_BOOTSTRAP.md](../docs/GREENFIELD_BOOTSTRAP.md).

| Path | Purpose |
|------|---------|
| `cost-guardrails/` | Zero-spend budget + monthly cap + anomaly detection (free) — apply first |
| `github-app/` | GitHub App + AgentCore Identity wiring so agents get short-lived tokens (no PATs) |
| `environments/` | prod / staging / preview / sandbox (added in product Phase 1, SDLC P3) |
| `modules/` | Reusable modules (DynamoDB, S3, Step Functions, Lambda, Cognito) |

> Human-owned via CODEOWNERS. **No secret values are ever committed** — only variable
> declarations and SSM Parameter Store names.
