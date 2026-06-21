locals {
  environment = "dev"
  project     = "sectional-title-agent-platform"

  # Short prefix for all resource names in this env. Keep it tight (DynamoDB/Lambda names).
  name_prefix = "stak-dev"

  # ── AWS account ────────────────────────────────────────────────────────────
  # The dedicated AWS account. allowed_account_ids in the provider uses this as a
  # guardrail: terraform refuses to run against any other account.
  account_id = "596451157763"

  # ── GitHub repo trusted by the OIDC deploy role (bootstrap stack) ──────────
  github_owner  = "Jarod-Smithy"
  github_repo   = "sectional-title-agent-management-platform"
  github_branch = "main"
}
