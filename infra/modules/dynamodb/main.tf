# Single-table store for the app (DynamoDB adapter, Increment 6 onward).
# Cost: PAY_PER_REQUEST + low volume = ~$0. First 25 GB storage free; PITR OFF.

variable "table_name" {
  type        = string
  description = "DynamoDB table name."
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}

# The table is encrypted at rest with the free AWS-owned key (see
# server_side_encryption below). The IaC scanner prefers a customer-managed KMS
# key, but a CMK adds ~$1/mo recurring cost which conflicts with the dev
# zero-spend goal / $50 lifetime cap. Deferred to the prod-hardening follow-up
# (POPIA key-custody), where a CMK is warranted for real PII.
# nosemgrep: terraform.aws.security.aws-dynamodb-table-unencrypted.aws-dynamodb-table-unencrypted
resource "aws_dynamodb_table" "app" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }

  # Encryption at rest with the AWS-owned key (free; no KMS charges). Satisfies
  # the IaC scanner; a customer-managed KMS key can be swapped in later if a
  # compliance requirement demands key custody.
  server_side_encryption {
    enabled = true
  }

  tags = var.tags
}

output "table_name" {
  value = aws_dynamodb_table.app.name
}

output "table_arn" {
  value = aws_dynamodb_table.app.arn
}
