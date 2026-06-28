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

  # De-prototype edges (Increment 8):
  # - seed_enabled=true keeps the demo "Acacia Heights" dashboard populated in dev.
  # - documents_enabled=true provisions the private uploads bucket + presigned PUT/GET.
  # - email_enabled=true registers the SES from-identity below and attaches the scoped
  #   ses:SendEmail IAM. NOTE: a @gmail.com from-address won't pass DMARC for real
  #   delivery (no domain control); fine for SES sandbox testing to verified recipients.
  #   Replace with a domain-based identity (DKIM) for production.
  seed_enabled      = true
  documents_enabled = true
  email_enabled     = true
  email_from        = "agent.kiepersol@gmail.com"

  # AI-native SDLC (Increment 9): captured errors + approved feature requests
  # become labelled GitHub issues that the SDLC agent picks up.
  # - sdlc_enabled=true reads the GitHub PAT from Secrets Manager (stak/sdlc/github-pat
  #   in eu-west-1) at boot and attaches scoped secretsmanager:GetSecretValue IAM.
  # - approver_email gets the feature-request approval magic-links (over SES).
  # - public_base_url is the API origin the approval links point back to (set
  #   explicitly to avoid a Lambda↔API Gateway dependency cycle).
  sdlc_enabled    = true
  github_repo     = "Jarod-Smithy/sectional-title-agent-management-platform"
  approver_email  = "jarod.mark.smith@gmail.com"
  public_base_url = "https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com"

  # Browser origins allowed to call the API (FastAPI CORS) and to PUT documents
  # straight to S3 via presigned URLs. The live dashboard is served from this
  # CloudFront distribution; localhost stays for local dev against the live API.
  cors_allow_origins        = ["https://d2vcnwv2hywkdo.cloudfront.net", "http://localhost:8000", "http://localhost:3000"]
  documents_allowed_origins = ["https://d2vcnwv2hywkdo.cloudfront.net", "http://localhost:8000", "http://localhost:3000"]
}
