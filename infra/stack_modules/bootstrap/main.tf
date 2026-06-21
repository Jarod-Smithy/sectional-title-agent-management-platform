# BOOTSTRAP stack — one-time, account-level wiring deployed in the data-plane
# region (af-south-1). Today it is the GitHub Actions OIDC provider + deploy
# role; the cost guardrails live in infra/cost-guardrails/ and are applied
# first, standalone.

variable "project" { type = string }
variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "region_code" { type = string }

variable "github_owner" { type = string }
variable "github_repo" { type = string }
variable "github_branch" {
  type    = string
  default = "main"
}
variable "create_oidc_provider" {
  type    = bool
  default = true
}

module "tags" {
  source = "../../modules/tags"

  project     = var.project
  environment = var.environment
  stack       = "bootstrap"
}

module "github_oidc" {
  source = "../../modules/github_oidc"

  account_id           = var.account_id
  aws_region           = var.aws_region
  name_prefix          = var.name_prefix
  github_owner         = var.github_owner
  github_repo          = var.github_repo
  github_branch        = var.github_branch
  create_oidc_provider = var.create_oidc_provider
  tags                 = module.tags.tags
}

output "deploy_role_arn" {
  description = "→ GitHub Actions variable AWS_DEPLOY_ROLE_ARN"
  value       = module.github_oidc.deploy_role_arn
}

output "oidc_provider_arn" {
  value = module.github_oidc.oidc_provider_arn
}
