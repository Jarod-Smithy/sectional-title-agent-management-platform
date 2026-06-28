# SDLC-TRIGGER stack — eu-west-1 (SDLC control plane). A public API Gateway HTTP
# API receives the GitHub `issues` webhook and invokes the trigger Lambda, which
# verifies the HMAC signature and dispatches `ai-sdlc` issues to the AgentCore
# harness. Co-located with the harness in eu-west-1.

variable "project" { type = string }
variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "region_code" { type = string }

# ARN of the AgentCore harness the trigger invokes. Provisioned out-of-band via
# the AgentCore CLI (Terraform support pending); supplied as an input so this
# stack stays declarative.
variable "harness_arn" {
  type = string
}

module "tags" {
  source = "../../modules/tags"

  project     = var.project
  environment = var.environment
  stack       = "sdlc-trigger"
}

module "trigger" {
  source = "../../modules/sdlc_trigger"

  name_prefix = var.name_prefix
  aws_region  = var.aws_region
  account_id  = var.account_id
  harness_arn = var.harness_arn
  tags        = module.tags.tags
}

module "http_api" {
  source = "../../modules/http_api"

  name_prefix          = "${var.name_prefix}-sdlc"
  lambda_invoke_arn    = module.trigger.invoke_arn
  lambda_function_name = module.trigger.function_name
  tags                 = module.tags.tags
}

output "webhook_url" {
  description = "GitHub webhook Payload URL (point the repo webhook here)."
  value       = module.http_api.api_endpoint
}

output "webhook_secret" {
  description = "GitHub webhook secret (sensitive)."
  value       = module.trigger.webhook_secret
  sensitive   = true
}
