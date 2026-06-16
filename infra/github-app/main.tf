# STUB — GitHub App + AgentCore Identity wiring.
# Resources are intentionally commented out: P0 establishes the contract and
# variable surface only. No `terraform apply` is run, and no secret VALUES are
# committed (only the SSM Parameter Store parameter NAME is referenced).
#
# Fill these in at P0 completion once the GitHub App is registered and the
# AgentCore Identity provider is available in the chosen region (OQ1).
#
# Cost note: the App private key is stored in SSM Parameter Store as a
# SecureString (standard tier = free), not Secrets Manager (~$0.40/secret/mo).

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Reference (read) the GitHub App private key from SSM Parameter Store by name.
# The value lives only in Parameter Store (SecureString) — never in git or tfvars.
# data "aws_ssm_parameter" "github_app_key" {
#   name            = var.github_app_private_key_ssm_parameter
#   with_decryption = true
# }

# AgentCore Identity workload that brokers short-lived GitHub App installation
# tokens to the dev agents (no PATs). Replace with the concrete AgentCore
# Identity resource/module once finalised.
# resource "aws_bedrockagentcore_identity_workload" "sdlc" {
#   name = var.agentcore_identity_workload_name
#   # github_app:
#   #   app_id          = var.github_app_id
#   #   installation_id = var.github_app_installation_id
#   #   private_key_ref = var.github_app_private_key_ssm_parameter
#   # token_ttl_seconds = 3600  # short-lived
# }

# OIDC trust for GitHub Actions → AWS (deploys, no stored cloud creds).
# resource "aws_iam_role" "actions_oidc" {
#   name               = "stak-actions-oidc"
#   assume_role_policy = data.aws_iam_policy_document.actions_oidc_trust.json
# }

output "notes" {
  value = "Stub only. No resources created. See README.md for the auth contract."
}
