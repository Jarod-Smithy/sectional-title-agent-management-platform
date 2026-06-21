terraform {
  # `//` marks what terragrunt copies into its cache: the whole infra/ tree, so
  # the stack module's `../../modules/...` references resolve. infra/ is 4 levels
  # up from here (bootstrap → af-south-1 → dev → live → infra).
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/bootstrap"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

# account_id / project / environment / name_prefix / aws_region / region_code
# come from the root `inputs`. We only add the GitHub trust details here.
inputs = {
  github_owner  = local.env_vars.locals.github_owner
  github_repo   = local.env_vars.locals.github_repo
  github_branch = local.env_vars.locals.github_branch

  # Flip to false if a token.actions.githubusercontent.com OIDC provider already
  # exists in the account (only one allowed per account).
  create_oidc_provider = true
}
