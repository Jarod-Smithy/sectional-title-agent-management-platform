# ---------------------------------------------------------------------------------------------------------------------
# ROOT TERRAGRUNT CONFIGURATION
# Mirrors the aip-idp pattern: a single root that generates the AWS provider + S3/DynamoDB remote state, read from
# the nearest env.hcl (environment-level) and region.hcl (region-level) files. Individual stacks live under
# live/<env>/<region>/<stack>/ and only `include` this root + point at a stack_module.
# ---------------------------------------------------------------------------------------------------------------------

locals {
  # Walk up the tree to the environment- and region-level variable files.
  env_vars    = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  region_vars = read_terragrunt_config(find_in_parent_folders("region.hcl"))

  environment = local.env_vars.locals.environment
  account_id  = local.env_vars.locals.account_id
  project     = local.env_vars.locals.project
  name_prefix = local.env_vars.locals.name_prefix

  aws_region        = local.region_vars.locals.region
  region_code       = local.region_vars.locals.region_code
  region_role       = local.region_vars.locals.role
  state_bucket_name = local.region_vars.locals.state_bucket_name
  lock_table_name   = "terraform-locks"
}

# Generate the AWS provider. Region comes from region.hcl, so af-south-1 stacks and eu-west-1 stacks each get the
# right provider automatically. allowed_account_ids is a guardrail: terraform refuses to run against the wrong account.
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region              = "${local.aws_region}"
  allowed_account_ids = ["${local.account_id}"]

  default_tags {
    tags = {
      Project     = "${local.project}"
      Environment = "${local.environment}"
      Region      = "${local.aws_region}"
      RegionRole  = "${local.region_role}"
      ManagedBy   = "terragrunt"
    }
  }
}
EOF
}

# Pin terraform + provider versions for every stack.
generate "version" {
  path      = "version.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}
EOF
}

# Remote state in S3 with a DynamoDB lock table. Terragrunt auto-creates the bucket + table on first run, so there is
# no manual bootstrap step. State is partitioned per env/region/stack via path_relative_to_include().
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = local.state_bucket_name
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = local.lock_table_name
  }
}

# Inputs every stack module can rely on. Stack-level terragrunt.hcl files add their own on top of these.
inputs = {
  account_id  = local.account_id
  project     = local.project
  environment = local.environment
  name_prefix = local.name_prefix
  aws_region  = local.aws_region
  region_code = local.region_code
}
