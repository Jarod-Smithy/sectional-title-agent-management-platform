terraform {
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/app"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

# All inputs (account_id, name_prefix, aws_region, ...) come from the root.
# Override resource sizing here if needed; defaults stay inside the free tier.
inputs = {
  # Bedrock inference is live, so size the function for real Converse latency
  # (API Gateway caps at 30s). Still well within free-tier-ish cost.
  lambda_memory_mb   = 512
  lambda_timeout_s   = 29
  log_retention_days = 14

  # Cognito JWT enforcement ON (ADR-0004). Every route except /api/health now
  # requires a valid Cognito access token. The pool/client are provisioned by
  # this stack; flip back to false to disable enforcement without destroying them.
  auth_enabled = true

  # PRODUCTION posture: durable DynamoDB storage + real Bedrock inference.
  # - repo_backend=dynamodb routes the API at the (already-provisioned) single
  #   table instead of ephemeral SQLite on /tmp.
  # - bedrock_enabled=true sets STAK_LLM_PROVIDER=bedrock AND attaches the
  #   scoped Bedrock InvokeModel IAM (cross-region Claude in eu-west-1).
  repo_backend    = "dynamodb"
  bedrock_enabled = true
}
