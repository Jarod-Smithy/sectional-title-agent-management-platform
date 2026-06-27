# APP stack — the product/data plane in af-south-1:
#   API Gateway (HTTP) → Lambda (FastAPI/Mangum) → DynamoDB (single table).
# Everything sits inside the AWS free tier for low traffic. The Lambda CODE is
# shipped by the deploy workflow via the OIDC role from the bootstrap stack;
# this stack only owns the infrastructure shell.

variable "project" { type = string }
variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "region_code" { type = string }

variable "lambda_memory_mb" {
  type    = number
  default = 256
}
variable "lambda_timeout_s" {
  type    = number
  default = 15
}
variable "log_retention_days" {
  type    = number
  default = 14
}
variable "cors_allow_origins" {
  type    = list(string)
  default = ["*"]
}

# Auth toggle: the Cognito pool is provisioned regardless, but enforcement on
# the API stays OFF until a trustee user exists and the dashboard sends tokens.
# Flip to true (and redeploy) to require Cognito access tokens on every route
# except /api/health.
variable "auth_enabled" {
  type    = bool
  default = false
}

# Bedrock inference plane (Increment 7). Off by default = provider stays 'stub'
# (zero-spend) and NO Bedrock IAM is attached. Flip to true (and redeploy) to
# route agent-assist through cross-region Claude in `bedrock_inference_region`.
variable "bedrock_enabled" {
  type    = bool
  default = false
}

variable "bedrock_inference_region" {
  type    = string
  default = "eu-west-1"
}

# Repository backend for the API. Defaults to ephemeral SQLite (dev-safe, on
# Lambda /tmp). Set to "dynamodb" for durable single-table storage; the table
# and the Lambda's DynamoDB IAM are provisioned by this stack regardless, so
# flipping this is the only step needed to use durable storage.
variable "repo_backend" {
  type    = string
  default = "sqlite"

  validation {
    condition     = contains(["sqlite", "dynamodb"], var.repo_backend)
    error_message = "repo_backend must be either \"sqlite\" or \"dynamodb\"."
  }
}

# Demo seeding. Off by default so real deployments never auto-populate the
# sample "Acacia Heights" scheme; the dev live stack opts in to keep the demo
# dashboard populated. Drives STAK_SEED_ENABLED.
variable "seed_enabled" {
  type    = bool
  default = false
}

# Outbound email plane (Increment 8). Off by default = provider stays 'log' (a
# dev-safe no-op that only records the interaction) and NO SES identity/IAM is
# created. Flip to true (and set email_from) to register an SES email identity
# and route approved/auto-filed replies through it. NOTE: the from-identity must
# be confirmed out-of-band via the link SES emails before delivery works.
variable "email_enabled" {
  type    = bool
  default = false
}

variable "email_from" {
  type    = string
  default = ""
}

# Document-upload plane (Increment 8). Off by default = no S3 bucket/IAM and the
# upload endpoints return 503 (paste-text path still works). Flip to true to
# provision the private uploads bucket and enable presigned PUT/GET.
variable "documents_enabled" {
  type    = bool
  default = false
}

variable "documents_allowed_origins" {
  type    = list(string)
  default = ["*"]
}

module "tags" {
  source = "../../modules/tags"

  project     = var.project
  environment = var.environment
  stack       = "app"
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  table_name = "${var.name_prefix}-platform"
  tags       = module.tags.tags
}

module "cognito" {
  source = "../../modules/cognito"

  name_prefix = var.name_prefix
  tags        = module.tags.tags
}

# Outbound email identity (SES) — only created when email_enabled. The
# from-address must be verified out-of-band (SES emails a confirmation link)
# before delivery works; until then keep provider "log".
module "ses" {
  source = "../../modules/ses"
  count  = var.email_enabled ? 1 : 0

  email_address = var.email_from
}

# Private uploads bucket (S3) — only created when documents_enabled. Bucket
# names are global, so suffix with the account id for uniqueness.
module "s3_docs" {
  source = "../../modules/s3_docs"
  count  = var.documents_enabled ? 1 : 0

  bucket_name     = "${var.name_prefix}-docs-${var.account_id}"
  allowed_origins = var.documents_allowed_origins
}

module "lambda_api" {
  source = "../../modules/lambda_api"

  name_prefix              = var.name_prefix
  aws_region               = var.aws_region
  account_id               = var.account_id
  dynamodb_table_name      = module.dynamodb.table_name
  dynamodb_table_arn       = module.dynamodb.table_arn
  memory_mb                = var.lambda_memory_mb
  timeout_s                = var.lambda_timeout_s
  log_retention_days       = var.log_retention_days
  bedrock_enabled          = var.bedrock_enabled
  bedrock_inference_region = var.bedrock_inference_region
  email_identity_arn       = var.email_enabled ? module.ses[0].identity_arn : ""
  documents_bucket_arn     = var.documents_enabled ? module.s3_docs[0].bucket_arn : ""
  email_enabled            = var.email_enabled
  documents_enabled        = var.documents_enabled
  tags                     = module.tags.tags

  # Cognito auth wiring. The verifier only fetches the pool's public JWKS over
  # HTTPS (no IAM perms needed), so no extra Lambda policy is required.
  extra_env = {
    STAK_AUTH_ENABLED             = tostring(var.auth_enabled)
    STAK_COGNITO_USER_POOL_ID     = module.cognito.user_pool_id
    STAK_COGNITO_CLIENT_ID        = module.cognito.client_id
    STAK_COGNITO_REGION           = var.aws_region
    STAK_LLM_PROVIDER             = var.bedrock_enabled ? "bedrock" : "stub"
    STAK_BEDROCK_INFERENCE_REGION = var.bedrock_inference_region
    STAK_REPO_BACKEND             = var.repo_backend
    STAK_SEED_ENABLED             = tostring(var.seed_enabled)
    STAK_EMAIL_PROVIDER           = var.email_enabled ? "ses" : "log"
    STAK_EMAIL_FROM               = var.email_from
    STAK_DOCUMENTS_BUCKET         = var.documents_enabled ? module.s3_docs[0].bucket_name : ""
  }
}

module "http_api" {
  source = "../../modules/http_api"

  name_prefix          = var.name_prefix
  lambda_invoke_arn    = module.lambda_api.invoke_arn
  lambda_function_name = module.lambda_api.function_name
  cors_allow_origins   = var.cors_allow_origins
  tags                 = module.tags.tags
}

output "api_endpoint" {
  description = "Public base URL → GitHub Actions variable API_ENDPOINT (smoke test)."
  value       = module.http_api.api_endpoint
}

output "lambda_function_name" {
  value = module.lambda_api.function_name
}

output "lambda_layer_name" {
  value = module.lambda_api.layer_name
}

output "dynamodb_table" {
  value = module.dynamodb.table_name
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_client_id" {
  value = module.cognito.client_id
}

output "cognito_issuer" {
  value = module.cognito.issuer
}
