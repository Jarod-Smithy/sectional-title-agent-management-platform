# Example inputs — copy to terraform.tfvars (git-ignored) and fill in.
# These are PLACEHOLDERS. Never commit real IDs/ARNs or any secret values.

aws_region                           = "eu-central-1"
github_owner                         = "your-org"
github_repo                          = "sectional-title-agent-platform"
github_app_id                        = "000000"
github_app_installation_id           = "00000000"
github_app_private_key_ssm_parameter = "/stak/sdlc/github-app/private-key"
agentcore_identity_workload_name     = "stak-sdlc-agents"
actions_oidc_role_arn                = "arn:aws:iam::000000000000:role/stak-actions-oidc"
