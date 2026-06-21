terraform {
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/inference"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

# Placeholder stack (Increment 7: Bedrock/AgentCore). No inputs beyond the root.
inputs = {}
