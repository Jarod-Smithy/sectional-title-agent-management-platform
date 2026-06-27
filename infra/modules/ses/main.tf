# Amazon SES sending identity for outbound trustee replies (Increment 8).
#
# Dev posture: a single VERIFIED EMAIL-ADDRESS identity (not a domain). On
# create, SES emails a confirmation link to `email_address`; the from-address
# cannot send until that link is clicked — a MANUAL, out-of-band step (there is
# no Terraform/API way to auto-confirm an email identity). Domain identities +
# DKIM are the prod-hardening follow-up. Cost: SES identities are free; you only
# pay per message — $0 at dev volume. SES sending IS available in af-south-1.

variable "email_address" {
  type        = string
  description = "From-address to register as an SES email identity (confirmed via the link SES sends)."
}

resource "aws_ses_email_identity" "from" {
  email = var.email_address
}

output "identity_arn" {
  description = "ARN of the SES email identity (scopes the Lambda ses:SendEmail policy)."
  value       = aws_ses_email_identity.from.arn
}

output "email_address" {
  description = "The registered from-address."
  value       = aws_ses_email_identity.from.email
}
