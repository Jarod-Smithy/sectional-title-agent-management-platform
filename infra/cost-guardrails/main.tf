# Cost guardrails for a greenfield, cost-sensitive AWS account.
# Everything here is FREE: the first 2 AWS Budgets are free, and AWS Cost
# Anomaly Detection has no charge. Apply this FIRST, right after the account
# is created, so spend can never surprise you.
#
#   terraform init
#   terraform apply -var="notification_email=you@example.com"
#
# Billing/Cost services are global and served from us-east-1.

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1" # Cost Explorer / Budgets endpoint
}

# 1) Zero-spend budget: alerts the moment ANY real charge appears (> $0.01).
#    Your early-warning that you have left the free tier.
resource "aws_budgets_budget" "zero_spend" {
  name         = "stak-zero-spend"
  budget_type  = "COST"
  limit_amount = "0.01"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }
}

# 2) Monthly cap budget: forecast + actual alerts at 50/80/100% of your ceiling.
resource "aws_budgets_budget" "monthly_cap" {
  name         = "stak-monthly-cap"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = toset(["50", "80", "100"])
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = tonumber(notification.value)
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.notification_email]
    }
  }

  # Forecasted overspend warning before the money is actually gone.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.notification_email]
  }
}

# 3) Cost Anomaly Detection: ML-based, free. Flags unusual per-service spend.
# NOTE: AWS auto-provisions one default SERVICE-dimension monitor per account
# ("Default-Services-Monitor"), and the account limit for DIMENSIONAL/SERVICE
# monitors is 1. On a fresh account, import that monitor before the first apply:
#   aws ce get-anomaly-monitors --query 'AnomalyMonitors[?MonitorDimension==`SERVICE`].MonitorArn'
#   terraform import aws_ce_anomaly_monitor.services <monitor-arn>
# Applying then renames it to "stak-service-monitor" in place (name is updatable).
resource "aws_ce_anomaly_monitor" "services" {
  name              = "stak-service-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "alerts" {
  name             = "stak-anomaly-alerts"
  frequency        = "DAILY"
  monitor_arn_list = [aws_ce_anomaly_monitor.services.arn]

  subscriber {
    type    = "EMAIL"
    address = var.notification_email
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = [var.anomaly_alert_threshold_usd]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}
