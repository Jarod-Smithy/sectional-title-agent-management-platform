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

module "lambda_api" {
  source = "../../modules/lambda_api"

  name_prefix         = var.name_prefix
  aws_region          = var.aws_region
  dynamodb_table_name = module.dynamodb.table_name
  dynamodb_table_arn  = module.dynamodb.table_arn
  memory_mb           = var.lambda_memory_mb
  timeout_s           = var.lambda_timeout_s
  log_retention_days  = var.log_retention_days
  tags                = module.tags.tags

  # Cognito auth wiring. The verifier only fetches the pool's public JWKS over
  # HTTPS (no IAM perms needed), so no extra Lambda policy is required.
  extra_env = {
    STAK_AUTH_ENABLED         = tostring(var.auth_enabled)
    STAK_COGNITO_USER_POOL_ID = module.cognito.user_pool_id
    STAK_COGNITO_CLIENT_ID    = module.cognito.client_id
    STAK_COGNITO_REGION       = var.aws_region
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
