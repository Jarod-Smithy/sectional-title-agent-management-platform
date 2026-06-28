# SDLC webhook trigger — eu-west-1. A GitHub `issues` webhook hits an API Gateway
# HTTP API, which invokes this Lambda. The Lambda verifies the HMAC signature and
# (for `ai-sdlc`-labelled issues) asynchronously invokes the AgentCore harness.
#
# The Lambda CODE is shipped inline here (single stdlib+boto3 file, no deps) via
# archive_file — unlike the product API it needs no separate CI deploy.

variable "name_prefix" {
  type        = string
  description = "Resource name prefix."
}

variable "aws_region" {
  type        = string
  description = "Region (eu-west-1; co-located with the harness)."
}

variable "account_id" {
  type        = string
  description = "AWS account id (scopes IAM resources)."
}

variable "harness_arn" {
  type        = string
  description = "ARN of the AgentCore harness to invoke."
}

variable "trigger_label" {
  type        = string
  description = "GitHub issue label that triggers the agent."
  default     = "ai-sdlc"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  function_name = "${var.name_prefix}-sdlc-trigger"
  function_arn  = "arn:aws:lambda:${var.aws_region}:${var.account_id}:function:${var.name_prefix}-sdlc-trigger"
}

# ── Webhook HMAC secret (generated, stored in Secrets Manager) ───────────────
resource "random_password" "webhook" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "webhook" {
  name        = "${var.name_prefix}/sdlc/github-webhook-secret"
  description = "GitHub webhook HMAC secret for the SDLC trigger."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "webhook" {
  secret_id     = aws_secretsmanager_secret.webhook.id
  secret_string = random_password.webhook.result
}

# ── Execution role ───────────────────────────────────────────────────────────
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "exec" {
  name               = "${local.function_name}-exec"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "perms" {
  statement {
    sid    = "InvokeHarness"
    effect = "Allow"
    # invoke_harness maps to the InvokeAgentRuntime IAM action on the harness.
    actions   = ["bedrock-agentcore:InvokeAgentRuntime", "bedrock-agentcore:InvokeHarness"]
    resources = [var.harness_arn, "${var.harness_arn}/*"]
  }
  statement {
    sid       = "ReadWebhookSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.webhook.arn]
  }
  statement {
    sid       = "SelfInvokeAsync"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [local.function_arn]
  }
}

resource "aws_iam_role_policy" "perms" {
  name   = local.function_name
  role   = aws_iam_role.exec.id
  policy = data.aws_iam_policy_document.perms.json
}

# ── Function ─────────────────────────────────────────────────────────────────
data "archive_file" "code" {
  type        = "zip"
  source_file = "${path.module}/handler.py"
  output_path = "${path.module}/build/sdlc_trigger.zip"
}

resource "aws_cloudwatch_log_group" "fn" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "trigger" {
  function_name = local.function_name
  role          = aws_iam_role.exec.arn
  runtime       = "python3.12"
  architectures = ["x86_64"]
  handler       = "handler.handler"

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  # The async worker path drains the harness stream (can run minutes); 15min cap.
  memory_size = 256
  timeout     = 900

  environment {
    variables = {
      HARNESS_ARN         = var.harness_arn
      WEBHOOK_SECRET_NAME = aws_secretsmanager_secret.webhook.name
      SELF_FUNCTION_NAME  = local.function_name
      TRIGGER_LABEL       = var.trigger_label
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.logs,
    aws_cloudwatch_log_group.fn,
  ]
}

output "function_name" {
  value = aws_lambda_function.trigger.function_name
}

output "invoke_arn" {
  value = aws_lambda_function.trigger.invoke_arn
}

output "webhook_secret" {
  description = "HMAC secret to configure on the GitHub webhook."
  value       = random_password.webhook.result
  sensitive   = true
}
