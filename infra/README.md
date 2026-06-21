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

## Layout (Terragrunt + Terraform — mirrors the aip-idp pattern)

| Path               | Purpose                                                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `cost-guardrails/` | Zero-spend budget + monthly cap + anomaly detection (free) — **apply first**, standalone (local state, us-east-1 billing) |
| `github-app/`      | GitHub App + AgentCore Identity wiring so agents get short-lived tokens (no PATs)                                         |
| `modules/`         | Small reusable Terraform modules (`tags`, `github_oidc`, `dynamodb`, `lambda_api`, `http_api`)                            |
| `stack_modules/`   | Composed stacks built from `modules/` (`bootstrap`, `app`, `inference`)                                                   |
| `live/`            | Terragrunt entrypoints: `live/<env>/<region>/<stack>/` — region is visible in the path                                    |

### `live/` tree

```
live/
  root.hcl                       # generates AWS provider + S3/DynamoDB remote state, reads env.hcl + region.hcl
  dev/
    env.hcl                      # account_id, name_prefix, github repo (env-level)
    af-south-1/                  # DATA PLANE (POPIA): product data resides in South Africa
      region.hcl                 # region + state bucket name
      bootstrap/                 # → stack_modules/bootstrap : GitHub OIDC provider + deploy role
      app/                       # → stack_modules/app       : API Gateway → Lambda → DynamoDB
    eu-west-1/                   # INFERENCE PLANE: Bedrock / AgentCore (no data at rest)
      region.hcl
      inference/                 # → stack_modules/inference : placeholder (Increment 7)
```

State lives in S3 (`stak-tfstate-<account_id>-<region>`) with a `terraform-locks` DynamoDB
table; terragrunt auto-creates both on first run. State is partitioned per `env/region/stack`.

### Bootstrap order

```bash
aws sso login                                              # short-lived admin creds (first run only)
terraform -chdir=infra/cost-guardrails init && terraform -chdir=infra/cost-guardrails apply   # budgets (free) — FIRST

export PATH="$PATH:$HOME/bin"                              # if terraform was installed via tfswitch
cd infra/live/dev/af-south-1/bootstrap && terragrunt apply  # GitHub OIDC role
cd ../app && terragrunt apply                               # DynamoDB + Lambda + API Gateway
# → copy the stack outputs into GitHub Actions repo VARIABLES (see .github/workflows/deploy.yml);
#   CI then deploys CODE via OIDC — no cloud keys are ever stored.
```

> Set `account_id` in `live/dev/env.hcl` before applying (it defaults to all-zeros, which
> makes terraform refuse to run — the safe default until the AWS account exists).

> Human-owned via CODEOWNERS. **No secret values are ever committed** — only variable
> declarations and SSM Parameter Store names.
