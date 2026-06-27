variable "name_prefix" {
  type        = string
  description = "Resource name prefix; the site bucket is named <prefix>-site."
}

variable "aws_region" {
  type        = string
  description = "Region the S3 origin bucket lives in (af-south-1 data plane)."
  default     = "af-south-1"
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}
