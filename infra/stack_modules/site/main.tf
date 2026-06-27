# SITE stack — static frontend hosting in the data-plane region (af-south-1):
#   S3 (private origin) → CloudFront (OAC, default *.cloudfront.net domain).
# A thin wrapper around modules/static_site, mirroring the app stack. Hosting
# cost ≈ $0 (free-tier S3 + CloudFront). The dashboard build is shipped by the
# deploy-frontend workflow; this stack only owns the hosting shell.

variable "project" { type = string }
variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "region_code" { type = string }

module "tags" {
  source = "../../modules/tags"

  project     = var.project
  environment = var.environment
  stack       = "site"
}

module "static_site" {
  source = "../../modules/static_site"

  name_prefix = var.name_prefix
  aws_region  = var.aws_region
  tags        = module.tags.tags
}

output "bucket_name" {
  description = "→ GitHub Actions variable SITE_BUCKET_NAME (s3 sync target)."
  value       = module.static_site.bucket_name
}

output "cloudfront_distribution_id" {
  description = "→ GitHub Actions variable SITE_CLOUDFRONT_ID (cache invalidation)."
  value       = module.static_site.cloudfront_distribution_id
}

output "cloudfront_domain_name" {
  description = "Public dashboard URL (*.cloudfront.net)."
  value       = module.static_site.cloudfront_domain_name
}
