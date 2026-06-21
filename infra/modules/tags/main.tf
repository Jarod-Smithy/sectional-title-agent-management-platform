# Tiny tags module (mirrors aip-idp's tags_module): a single place to compute the
# common tag set so every resource in a stack is labelled consistently. The
# provider already sets Project/Environment via default_tags; this adds the
# per-stack Stack tag and any extras.

variable "project" {
  type        = string
  description = "Project name."
}

variable "environment" {
  type        = string
  description = "Environment name (dev/prod/...)."
}

variable "stack" {
  type        = string
  description = "Stack name (bootstrap/app/inference)."
}

variable "extra_tags" {
  type        = map(string)
  description = "Additional tags to merge in."
  default     = {}
}

locals {
  tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Stack       = var.stack
      ManagedBy   = "terragrunt"
    },
    var.extra_tags,
  )
}

output "tags" {
  description = "Computed tag map."
  value       = local.tags
}
