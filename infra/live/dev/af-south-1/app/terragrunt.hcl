terraform {
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/app"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

# All inputs (account_id, name_prefix, aws_region, ...) come from the root.
# Override resource sizing here if needed; defaults stay inside the free tier.
inputs = {
  lambda_memory_mb   = 256
  lambda_timeout_s   = 15
  log_retention_days = 14

  # Cognito JWT enforcement ON (ADR-0004). Every route except /api/health now
  # requires a valid Cognito access token. The pool/client are provisioned by
  # this stack; flip back to false to disable enforcement without destroying them.
  auth_enabled = true
}
