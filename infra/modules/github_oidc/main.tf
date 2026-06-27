# GitHub Actions OIDC → AWS. The deploy workflow assumes the `deploy` role with
# NO stored cloud credentials; trust is pinned to ONE repo + branch.
#
# Scope note: the deploy policy is scoped to the function/layer NAME PREFIX
# (not a concrete ARN) so this bootstrap stack has no dependency on the app
# stack and can be applied first. CI may only update code/config + publish
# layers — never create or destroy infrastructure.

variable "account_id" {
  type        = string
  description = "AWS account id."
}

variable "aws_region" {
  type        = string
  description = "Region used for ARN construction in the deploy policy."
}

variable "name_prefix" {
  type        = string
  description = "Resource name prefix; deploy perms are scoped to <prefix>-*."
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user that owns the repo."
}

variable "github_repo" {
  type        = string
  description = "Repository name."
}

variable "github_branch" {
  type        = string
  description = "Branch allowed to assume the deploy role."
  default     = "main"
}

variable "create_oidc_provider" {
  type        = bool
  description = "Create the GitHub OIDC provider. Set false if one already exists in the account (only one allowed)."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}

# One OIDC provider per account. When create_oidc_provider=false we look it up by its well-known ARN.
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub Actions OIDC root CA thumbprint (public, well-known value).
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # pragma: allowlist secret
  tags            = var.tags
}

locals {
  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : "arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"

  function_arn_prefix = "arn:aws:lambda:${var.aws_region}:${var.account_id}:function:${var.name_prefix}-*"
  layer_arn_prefix    = "arn:aws:lambda:${var.aws_region}:${var.account_id}:layer:${var.name_prefix}-*"

  # Frontend static-site bucket (created by the separate `site` stack). Derived
  # from name_prefix the same way the lambda/layer ARNs are, so this bootstrap
  # stack stays dependency-free and can still be applied first.
  site_bucket_arn = "arn:aws:s3:::${var.name_prefix}-site"
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Only this repo on this branch may assume the role.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_owner}/${var.github_repo}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${var.name_prefix}-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
  tags               = var.tags
}

# Least privilege: update THIS project's functions + publish/read its layers only.
data "aws_iam_policy_document" "deploy_perms" {
  statement {
    sid    = "UpdateFunction"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:PublishVersion",
      "lambda:ListVersionsByFunction",
    ]
    resources = [local.function_arn_prefix]
  }

  statement {
    sid       = "PublishLayer"
    effect    = "Allow"
    actions   = ["lambda:PublishLayerVersion"]
    resources = [local.layer_arn_prefix]
  }

  statement {
    sid       = "ReadLayerVersions"
    effect    = "Allow"
    actions   = ["lambda:GetLayerVersion"]
    resources = ["${local.layer_arn_prefix}:*"]
  }

  # ── Frontend static-site deploy (S3 sync + CloudFront invalidation) ──────────
  # The deploy-frontend workflow syncs the exported Next.js build (frontend/out)
  # to the site bucket and invalidates the edge cache. Scoped to THIS project's
  # site bucket only. CloudFront invalidation can't be ARN-scoped at bootstrap
  # time (the distribution is created later by the `site` stack), so those two
  # actions use Resource "*" — invalidation is cache-only/non-destructive, so the
  # blast radius is negligible. No standing cost ($0).
  statement {
    sid    = "SyncSiteBucket"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      local.site_bucket_arn,
      "${local.site_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "InvalidateCloudFront"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${var.name_prefix}-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy_perms.json
}

output "deploy_role_arn" {
  description = "ARN the GitHub Actions deploy workflow assumes (→ AWS_DEPLOY_ROLE_ARN variable)."
  value       = aws_iam_role.deploy.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider in this account."
  value       = local.oidc_provider_arn
}
