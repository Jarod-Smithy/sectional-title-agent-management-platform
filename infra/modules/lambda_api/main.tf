# Lambda (FastAPI via Mangum) + execution role + log group.
#
# Terraform owns the function SHELL (role, runtime, env, handler); the deploy
# workflow owns the CODE + dependency layer. `ignore_changes` stops a later
# apply from reverting what CI shipped.

variable "name_prefix" {
  type        = string
  description = "Resource name prefix."
}

variable "aws_region" {
  type        = string
  description = "Region (passed into the function env for the runtime)."
}

variable "dynamodb_table_name" {
  type        = string
  description = "Name of the app DynamoDB table."
}

variable "dynamodb_table_arn" {
  type        = string
  description = "ARN of the app DynamoDB table (scopes the runtime policy)."
}

variable "account_id" {
  type        = string
  description = "AWS account id (scopes the Bedrock inference-profile ARN)."
}

variable "bedrock_enabled" {
  type        = bool
  description = "Attach the Bedrock InvokeModel policy. Off = no standing perms."
  default     = false
}

variable "bedrock_inference_region" {
  type        = string
  description = "Region of the Bedrock cross-region inference profile (Claude)."
  default     = "eu-west-1"
}

variable "memory_mb" {
  type        = number
  description = "Lambda memory (MB)."
  default     = 256
}

variable "timeout_s" {
  type        = number
  description = "Lambda timeout (s). API Gateway HTTP API caps integrations at 30s."
  default     = 15
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention (days)."
  default     = 14
}

variable "extra_env" {
  type        = map(string)
  description = "Additional environment variables merged into the function."
  default     = {}
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
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
  name               = "${var.name_prefix}-api-exec"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# X-Ray write permissions for active tracing (enabled below). Free tier covers
# 100k traces/month — effectively $0 at this volume.
resource "aws_iam_role_policy_attachment" "xray" {
  role       = aws_iam_role.exec.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Runtime access to the single table only.
data "aws_iam_policy_document" "dynamo" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [
      var.dynamodb_table_arn,
      "${var.dynamodb_table_arn}/index/*",
    ]
  }
}

resource "aws_iam_role_policy" "dynamo" {
  name   = "${var.name_prefix}-dynamo"
  role   = aws_iam_role.exec.id
  policy = data.aws_iam_policy_document.dynamo.json
}

# Bedrock model invocation — only when explicitly enabled (zero standing perms
# otherwise). Scoped to Anthropic Claude foundation-model copies across the EU
# geo and the account's EU cross-region inference profiles; never Resource "*".
data "aws_iam_policy_document" "bedrock" {
  count = var.bedrock_enabled ? 1 : 0

  statement {
    sid    = "InvokeClaude"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:${var.bedrock_inference_region}:${var.account_id}:inference-profile/eu.anthropic.claude-*",
      "arn:aws:bedrock:eu-*::foundation-model/anthropic.claude-*",
    ]
  }
}

resource "aws_iam_role_policy" "bedrock" {
  count  = var.bedrock_enabled ? 1 : 0
  name   = "${var.name_prefix}-bedrock"
  role   = aws_iam_role.exec.id
  policy = data.aws_iam_policy_document.bedrock[0].json
}

# ── Log group (explicit, so retention caps storage cost) ─────────────────────
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# ── Placeholder code so the function exists before the first CI deploy ───────
# The real app/main.py (Mangum `handler`) is shipped by the deploy workflow.
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/build/placeholder.zip"

  source {
    content  = "def handler(event, context):\n    return {'statusCode': 200, 'body': 'placeholder - awaiting first deploy'}\n"
    filename = "app/main.py"
  }
}

locals {
  base_env = {
    STAK_DATA_DIR     = "/tmp/data"
    STAK_SERVE_STATIC = "false"
    STAK_REPO_BACKEND = "sqlite"
    STAK_LLM_PROVIDER = "stub"
    STAK_DYNAMO_TABLE = var.dynamodb_table_name
    STAK_AWS_REGION   = var.aws_region
  }
}

resource "aws_lambda_function" "api" {
  function_name = "${var.name_prefix}-api"
  role          = aws_iam_role.exec.arn
  runtime       = "python3.12"
  architectures = ["x86_64"]
  handler       = "app.main.handler"

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  memory_size = var.memory_mb
  timeout     = var.timeout_s

  environment {
    variables = merge(local.base_env, var.extra_env)
  }

  # End-to-end request tracing (X-Ray). Permissions attached above.
  tracing_config {
    mode = "Active"
  }

  # CI owns code + layers; do not let terraform revert them.
  lifecycle {
    ignore_changes = [filename, source_code_hash, layers]
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.logs,
    aws_cloudwatch_log_group.api,
  ]
}

output "function_name" {
  value = aws_lambda_function.api.function_name
}

output "function_arn" {
  value = aws_lambda_function.api.arn
}

output "invoke_arn" {
  value = aws_lambda_function.api.invoke_arn
}

output "layer_name" {
  description = "Expected layer name CI publishes (matches the OIDC deploy policy prefix)."
  value       = "${var.name_prefix}-api-deps"
}
