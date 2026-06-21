# Public HTTP entrypoint: API Gateway HTTP API (cheaper than REST) with a single
# $default proxy route to the Lambda. Free tier: 1M requests/mo for 12 months.

variable "name_prefix" {
  type        = string
  description = "Resource name prefix."
}

variable "lambda_invoke_arn" {
  type        = string
  description = "invoke_arn of the target Lambda."
}

variable "lambda_function_name" {
  type        = string
  description = "Name of the target Lambda (for the invoke permission)."
}

variable "cors_allow_origins" {
  type        = list(string)
  description = "Allowed CORS origins."
  default     = ["*"]
}

variable "tags" {
  type        = map(string)
  description = "Tags to attach."
  default     = {}
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.name_prefix}-http"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.cors_allow_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
  }

  tags = var.tags
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  tags = var.tags
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "api_endpoint" {
  description = "Public base URL."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  value = aws_apigatewayv2_api.http.id
}
