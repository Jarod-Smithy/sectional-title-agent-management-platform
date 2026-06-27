terraform {
  # `//` marks what terragrunt copies into its cache: the whole infra/ tree, so
  # the stack module's `../../modules/...` references resolve. infra/ is 4 levels
  # up from here (site → af-south-1 → dev → live → infra).
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/site"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

# All inputs (account_id, project, environment, name_prefix, aws_region,
# region_code) come from the root `inputs`. The static-site stack needs nothing
# extra; defaults stay inside the free tier (~$0/mo).
inputs = {}
