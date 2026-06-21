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
}
