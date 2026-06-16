# GitHub App + AgentCore Identity (STUB)

How the SDLC agents authenticate **without any stored secrets/PATs**
([docs/AI_NATIVE_SDLC_DESIGN.md §12](../../docs/AI_NATIVE_SDLC_DESIGN.md)):

```
Dev agent (AgentCore Runtime)
   │ requests a credential
   ▼
AgentCore Identity  ──issues short-lived──►  GitHub App installation token
   │                                          (scoped, ~1h TTL)
   └──issues short-lived──►  AWS creds via OIDC (for deploys)
```

Principles:
- **No PATs, no long-lived secrets in code or CI.** The GitHub App's private key lives in
  **SSM Parameter Store** as a SecureString (standard tier = **free**); only its **name** is
  referenced here. (Parameter Store is used instead of Secrets Manager to avoid ~$0.40/secret/mo.)
- **Least privilege.** The App is granted only the permissions the agents need
  (contents, pull requests, issues, checks, actions) on this repo.
- **OIDC for AWS.** GitHub Actions assumes a role via OIDC; no cloud keys are stored.

## Files

| File | Purpose |
|------|---------|
| `variables.tf` | Inputs (ARNs, IDs) — **no secret values** |
| `main.tf` | Stub resources/wiring (commented; filled out in P0 completion) |
| `terraform.example.tfvars` | Example inputs (placeholders only) |

> This is a **stub**: it documents the contract and variable surface. No `apply` is run,
> and no real identifiers are committed. AgentCore Identity itself is provisioned via the
> **AgentCore CLI / CDK** (region `eu-central-1`); Terraform here covers the GitHub App
> key reference (SSM Parameter Store) + OIDC role wiring.
>
> Store the key once (free) with:
> `aws ssm put-parameter --name /stak/sdlc/github-app/private-key --type SecureString --value file://app-key.pem`
