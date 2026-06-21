# INFERENCE stack — eu-west-1 (inference plane). Placeholder for Increment 7
# (Bedrock LLM adapter + AgentCore). af-south-1 has no Bedrock, so model
# invocation runs here; only transient prompt payloads cross the border, nothing
# is stored. This stack intentionally creates NO resources yet (zero cost) and
# exists so the two-region terragrunt wiring is in place and validates today.
#
# When wired up it will hold, e.g.:
#   - an IAM policy granting the app Lambda's exec role bedrock:InvokeModel on
#     the eu-west-1 model ARNs (attached cross-stack),
#   - AgentCore runtime configuration (deployed via the AgentCore CLI/CDK; see
#     infra/README.md — Terraform support "coming soon").

variable "project" { type = string }
variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "region_code" { type = string }

locals {
  # Model invocation region for the runtime (BEDROCK_REGION env var on the app Lambda).
  bedrock_region = var.aws_region
}

output "bedrock_region" {
  description = "Region the app Lambda should target for Bedrock/AgentCore calls."
  value       = local.bedrock_region
}
