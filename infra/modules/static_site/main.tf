# Static-site hosting for the Next.js dashboard: a private S3 origin fronted by
# CloudFront via Origin Access Control (OAC). The bucket is never public; only
# the distribution can read it. Cost ≈ $0 — S3 storage for a few MB of static
# assets and CloudFront sit inside the AWS free tier at this traffic. The build
# (frontend/out) is shipped by the deploy-frontend workflow, NOT terraform.
#
# POPIA note: CloudFront edge caches only public JS/HTML/CSS (no PII); all
# personal data stays behind the af-south-1 data-plane API. So the global edge
# footprint is POPIA-neutral. The origin bucket itself stays in af-south-1.

locals {
  bucket_name = "${var.name_prefix}-site"
}

# ── Private origin bucket ────────────────────────────────────────────────────
# Encryption at rest with the free AWS-owned/S3-managed key (AES256); a
# customer-managed KMS key adds ~$1/mo recurring cost which conflicts with the
# zero-spend dev goal. Versioning is OFF (no extra storage cost); the build is
# reproducible from CI so historical object versions add no value here.
# nosemgrep: terraform.aws.security.aws-s3-bucket-unencrypted.aws-s3-bucket-unencrypted
resource "aws_s3_bucket" "site" {
  bucket = local.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── CloudFront access to the private bucket (OAC, SigV4) ──────────────────────
resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-site-oac"
  description                       = "OAC for ${local.bucket_name}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# AWS-managed CachingOptimized policy (long TTLs, gzip/br). No custom policy to
# manage, and it is free.
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

# ── Security response headers ────────────────────────────────────────────────
# Pragmatic CSP: allow the SPA to load its own assets and call the af-south-1
# HTTP API + Cognito over connect-src. 'unsafe-inline' is permitted for script
# and style because Next's static export inlines hydration scripts and styled
# chunks; tightening to nonces/hashes is a prod-hardening follow-up.
resource "aws_cloudfront_response_headers_policy" "security" {
  name = "${var.name_prefix}-site-security-headers"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    content_security_policy {
      override = true
      content_security_policy = join(" ", [
        "default-src 'self';",
        "connect-src 'self' https://*.execute-api.af-south-1.amazonaws.com https://cognito-idp.af-south-1.amazonaws.com;",
        "img-src 'self' data:;",
        "script-src 'self' 'unsafe-inline';",
        "style-src 'self' 'unsafe-inline';",
        "font-src 'self' data:;",
        "object-src 'none';",
        "base-uri 'self';",
        "frame-ancestors 'none';",
      ])
    }
  }
}

# ── Distribution ─────────────────────────────────────────────────────────────
# PriceClass_100 (NA/EU edges only) keeps cost minimal. Uses the default
# *.cloudfront.net certificate — NO custom domain/ACM (those would need a
# us-east-1 cert; not used here). SPA fallback: 403/404 → /index.html (200) so
# deep links and client-side routes resolve to the app shell.
#
# nosemgrep justification: the default *.cloudfront.net certificate is fixed to
# TLSv1 by AWS; minimum_protocol_version cannot be raised to TLSv1.2_2021
# without a custom domain + ACM certificate (intentionally avoided for cost).
# Viewer traffic is still forced to HTTPS via viewer_protocol_policy below.
# nosemgrep: terraform.aws.security.aws-cloudfront-insecure-tls.aws-insecure-cloudfront-distribution-tls-version
resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.name_prefix} static dashboard"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-${local.bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id           = "s3-${local.bucket_name}"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Default CloudFront certificate (*.cloudfront.net). No custom domain → no ACM.
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}

# ── Bucket policy: only this distribution (via OAC) may read objects ──────────
data "aws_iam_policy_document" "site" {
  statement {
    sid       = "AllowCloudFrontOACRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site.json
}
