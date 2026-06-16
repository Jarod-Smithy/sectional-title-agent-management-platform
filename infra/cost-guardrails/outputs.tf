output "zero_spend_budget" {
  description = "Name of the zero-spend budget that fires on any real charge."
  value       = aws_budgets_budget.zero_spend.name
}

output "monthly_cap_budget" {
  description = "Name of the monthly ceiling budget."
  value       = aws_budgets_budget.monthly_cap.name
}

output "anomaly_monitor_arn" {
  description = "ARN of the Cost Anomaly Detection monitor."
  value       = aws_ce_anomaly_monitor.services.arn
}
