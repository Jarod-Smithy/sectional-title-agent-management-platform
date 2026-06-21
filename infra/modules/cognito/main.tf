# Cognito user pool — authentication for the dashboard API (Increment 6b).
# Cost: user pools are free for the first 50,000 MAU (basic tier). Advanced
# security features (the only paid add-on) are intentionally NOT enabled, so
# this stays at ~$0 and within the zero-spend dev goal / $50 lifetime cap.

variable "name_prefix" {
  type        = string
  description = "Resource name prefix, e.g. 'stak-dev'."
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}

# Invite-only: trustees are created by an administrator, so self-service signup
# is disabled. Keeps the pool closed to the public.
resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  # No public sign-up; admins invite trustees explicitly.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # MFA is OFF for the dev pool: SMS MFA incurs per-message cost and TOTP adds
  # onboarding friction before any real users exist. Revisit in prod-hardening
  # (POPIA) where MFA for trustees is warranted. Advanced Security ("audit"/
  # "enforced") is the paid feature and stays disabled.
  # checkov:skip=CKV_AWS_171:MFA deferred to prod-hardening (zero-spend dev pool)
  mfa_configuration = "OFF"

  tags = var.tags
}

# App client for the SPA dashboard: public client (no secret), SRP auth only.
resource "aws_cognito_user_pool_client" "this" {
  name         = "${var.name_prefix}-dashboard"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Don't reveal whether a username exists on failed auth.
  prevent_user_existence_errors = "ENABLED"
}

output "user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "client_id" {
  value = aws_cognito_user_pool_client.this.id
}

output "issuer" {
  description = "Expected 'iss' claim / JWKS base for verifying access tokens."
  value       = "https://${aws_cognito_user_pool.this.endpoint}"
}
