locals {
  # ── Inference plane: Bedrock / AgentCore (no POPIA data at rest) ────────────
  # af-south-1 has no Bedrock, so model calls run from the nearest compliant
  # region (EU/GDPR = adequate protection under POPIA §72). Only transient
  # prompt payloads cross the border; nothing is stored here.
  region      = "eu-west-1"
  region_code = "euw1"
  role        = "inference-plane"

  env_vars   = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  account_id = local.env_vars.locals.account_id

  state_bucket_name = "stak-tfstate-${local.account_id}-${local.region}"
}
