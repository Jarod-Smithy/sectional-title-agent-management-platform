# Policy-as-code (OPA / Conftest)

Organisation guardrails enforced on **Terraform** before any plan can merge or
deploy — the gap **G4** from [docs/AI_NATIVE_BUILD_PLAN.md](../docs/AI_NATIVE_BUILD_PLAN.md) §2.
These rules sit **on top of** tfsec/Trivy + Checkov (which catch generic
misconfigurations); Conftest encodes _our_ scheme-specific, non-negotiable rules:

| Policy    | Rule                                                               | Vision/Plan basis               |
| --------- | ------------------------------------------------------------------ | ------------------------------- |
| `region`  | All resources must be in **af-south-1** (SA data residency).       | Vision §5 (data residency)      |
| `s3`      | **No public** S3 buckets/ACLs; block public access must be on.     | OWASP / no data leakage         |
| `iam`     | **No wildcard** (`*`) IAM actions or resources.                    | least-privilege (Plan §2 G4)    |
| `secrets` | No plaintext secrets in resource attributes; use SSM SecureString. | Plan P0.5 #13 (no stored creds) |

## How it runs

- **CI:** the `policy` job in [.github/workflows/ci.yml](../.github/workflows/ci.yml)
  runs `conftest test` against every Terraform plan rendered to JSON. It is a
  **required** check via the `All gates` aggregator. When no `.tf` files exist
  yet (P0 skeleton) the job passes cleanly.
- **Local:** `conftest test infra/ --policy policy/` (after `terraform show -json`
  for plan-level checks).

## Conventions

- Each `deny[msg]` rule returns a human-readable violation string.
- Rules live under `package main` so Conftest picks them up by default.
- Tests for the policies live in `*_test.rego` and run with `conftest verify`.
