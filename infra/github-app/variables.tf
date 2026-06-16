# Input surface for the GitHub App + AgentCore Identity wiring.
# NOTE: declarations only — never assign secret values here. The GitHub App
# private key VALUE lives only in SSM Parameter Store (SecureString, free);
# Terraform references it by NAME and decrypts at apply time — never in git.

variable "aws_region" {
  description = "Region for the SDLC control-plane (code only; no POPIA data). AgentCore managed harness runs in Frankfurt. Product data stays in af-south-1 (OQ1)."
  type        = string
  default     = "eu-central-1"
}

variable "github_owner" {
  description = "GitHub org/user that owns the repository."
  type        = string
}

variable "github_repo" {
  description = "Repository name."
  type        = string
  default     = "sectional-title-agent-platform"
}

variable "github_app_id" {
  description = "GitHub App ID (not a secret)."
  type        = string
}

variable "github_app_installation_id" {
  description = "GitHub App installation ID for this repo (not a secret)."
  type        = string
}

variable "github_app_private_key_ssm_parameter" {
  description = "Name of the SSM Parameter Store SecureString holding the GitHub App private key (free tier). The VALUE is never stored in git."
  type        = string
  default     = "/stak/sdlc/github-app/private-key"
}

variable "agentcore_identity_workload_name" {
  description = "AgentCore Identity workload/identity that brokers short-lived tokens to the dev agents."
  type        = string
  default     = "stak-sdlc-agents"
}

variable "actions_oidc_role_arn" {
  description = "IAM role assumed by GitHub Actions via OIDC for deploys (no stored cloud creds)."
  type        = string
  default     = ""
}
