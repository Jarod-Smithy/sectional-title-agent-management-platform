output "bucket_name" {
  description = "Name of the private S3 origin bucket → GitHub variable SITE_BUCKET_NAME."
  value       = aws_s3_bucket.site.id
}

output "bucket_arn" {
  value = aws_s3_bucket.site.arn
}

output "cloudfront_distribution_id" {
  description = "Distribution id → GitHub variable SITE_CLOUDFRONT_ID (cache invalidation)."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  description = "Public *.cloudfront.net URL the dashboard is served from."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_distribution_arn" {
  value = aws_cloudfront_distribution.site.arn
}
