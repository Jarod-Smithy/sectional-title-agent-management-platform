terraform {
  source = "${get_terragrunt_dir()}/../../../..//stack_modules/sdlc_trigger"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

# The AgentCore harness ARN (provisioned via the AgentCore CLI in eu-west-1).
# Update if the harness is recreated.
inputs = {
  harness_arn = "arn:aws:bedrock-agentcore:eu-west-1:596451157763:harness/stak_sdlc_agent-SoN87gqXRC"
}
