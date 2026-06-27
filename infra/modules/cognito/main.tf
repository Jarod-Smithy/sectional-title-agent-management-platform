# Cognito user pool — authentication for the dashboard API (Increment 6b).
# Cost: user pools are free for the first 50,000 MAU (basic tier). Advanced
# security features (the only paid add-on) are intentionally NOT enabled, so
# this stays at ~$0 and within the zero-spend dev goal / $50 lifetime cap.
#
# Future upgrade (NOT in this change, scope discipline): the Cognito
# "Essentials"/"Plus" feature plans unlock passkeys (WebAuthn), the USER_AUTH
# choice-based sign-in flow, managed login UI, and threat protection. At our
# MAU (~low double-digits) these tiers are cost-trivial (pennies/month), but
# enabling them is a separate decision and deliberately left out here.

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

  # TOTP (software-token) MFA is now ON as OPTIONAL. Software tokens are free
  # (no per-message cost), so this stays within the $50/month budget. SMS MFA is
  # intentionally NOT enabled because it bills per message. Enforcement can later
  # move OPTIONAL->ON once all trustees have enrolled an authenticator app.
  # checkov:skip=CKV_AWS_171:TOTP MFA enabled as OPTIONAL; SMS intentionally off (per-message cost)
  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

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

  # Short-lived access token (15 min) shrinks the theft/replay window if a token
  # leaks; the long-lived refresh token (30d) keeps trustees signed in. Id token
  # also 15 min to match. Note: access_token uses "minutes" units below.
  access_token_validity  = 15
  id_token_validity      = 15
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
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
