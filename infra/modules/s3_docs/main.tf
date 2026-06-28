# Private S3 bucket for trustee document uploads (Increment 8, presigned PUT/GET).
#
# Locked down: all public access blocked, bucket-owner-enforced (ACLs off),
# SSE-S3 (AES256 — free, no KMS spend), and a CORS rule so the browser can PUT
# (presigned upload) and GET directly from the dashboard origin. A lifecycle
# rule expires objects after `retention_days` to cap storage cost. Versioning is
# left OFF (dev cost posture). Cost: first 5 GB + requests are free tier — ~$0 at
# dev volume; the lifecycle expiry bounds worst-case growth.

variable "bucket_name" {
  type        = string
  description = "Globally-unique S3 bucket name for uploaded documents."
}

variable "allowed_origins" {
  type        = list(string)
  description = "Origins permitted to PUT/GET via presigned URLs (browser CORS)."
  default     = ["*"]
}

variable "retention_days" {
  type        = number
  description = "Expire uploaded objects after this many days (storage-cost cap)."
  default     = 365
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}

resource "aws_s3_bucket" "docs" {
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket = aws_s3_bucket.docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  cors_rule {
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.allowed_origins
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    id     = "expire-uploads"
    status = "Enabled"

    filter {}

    expiration {
      days = var.retention_days
    }
  }
}

output "bucket_name" {
  value = aws_s3_bucket.docs.id
}

output "bucket_arn" {
  value = aws_s3_bucket.docs.arn
}
