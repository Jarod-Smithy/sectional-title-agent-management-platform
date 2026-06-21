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

  tags = var.tags
}

output "table_name" {
  value = aws_dynamodb_table.app.name
}

output "table_arn" {
  value = aws_dynamodb_table.app.arn
}
