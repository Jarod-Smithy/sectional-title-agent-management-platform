# Inputs for the cost guardrails. No secrets here.

variable "notification_email" {
  description = "Email address that receives budget + anomaly alerts."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.notification_email))
    error_message = "notification_email must be a valid email address."
  }
}

variable "monthly_budget_limit" {
  description = "Hard monthly USD ceiling for the whole account (alerts only; does not stop spend)."
  type        = string
  default     = "5"
}

variable "anomaly_alert_threshold_usd" {
  description = "Minimum anomalous spend (USD) before Cost Anomaly Detection emails you."
  type        = string
  default     = "10"
}
