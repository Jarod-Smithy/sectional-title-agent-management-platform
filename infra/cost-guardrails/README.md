# Cost Guardrails

The **first thing to apply** after creating the AWS account. Everything here is
**free** and exists so a greenfield, cost-sensitive account can never surprise you
with a bill.

## What it creates

| Resource                  | Purpose                                                                                           | Cost                 |
| ------------------------- | ------------------------------------------------------------------------------------------------- | -------------------- |
| `stak-zero-spend` budget  | Emails you the moment **any** real charge appears (> $0.01) — your "you left the free tier" alarm | Free (1st 2 budgets) |
| `stak-monthly-cap` budget | Actual alerts at 50/80/100% + a forecast alert for a small monthly ceiling                        | Free                 |
| Cost Anomaly Detection    | ML flags unusual per-service spend (e.g., a runaway Bedrock loop)                                 | Free                 |

> Budgets and anomaly alerts **notify only** — they do not stop spend. The hard stop
> is operational: iteration/token caps in the agents (§3.2, R1) and not standing up
> Bedrock/AgentCore until P1.

## Apply

```bash
cd infra/cost-guardrails
cp terraform.example.tfvars terraform.tfvars   # then edit notification_email
terraform init
terraform apply
```

Confirm the budget alert email (AWS sends a verification request the first time).

## Why this is separate from the rest of infra

Billing/Cost services are **global**, served from `us-east-1`, and should be applied
**before** anything else — independent of the `af-south-1` product stack and the
`eu-central-1` SDLC control-plane. Keeping it in its own state means you can stand the
guardrails up on day one with nothing else deployed.
