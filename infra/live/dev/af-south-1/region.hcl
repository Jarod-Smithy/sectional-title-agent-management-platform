locals {
  # ── Data plane (POPIA): product data resides in South Africa ───────────────
  region      = "af-south-1"
  region_code = "afs1"
  role        = "data-plane"

  # Pull the account id up from env.hcl so the state bucket name is globally unique.
  env_vars   = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  account_id = local.env_vars.locals.account_id

  # Terragrunt auto-creates this bucket + the terraform-locks table on first run.
  state_bucket_name = "stak-tfstate-${local.account_id}-${local.region}"
}
