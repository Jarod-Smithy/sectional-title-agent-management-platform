# Organisation guardrails for Terraform, enforced via Conftest.
# Input = `terraform show -json <plan>` (plan JSON). Rules are defensive: a
# missing attribute never crashes evaluation, it simply doesn't trigger a deny.
#
# Run:  conftest test plan.json --policy policy/
# Test: conftest verify --policy policy/
package main

import future.keywords.in

# Helper: every resource's planned end-state (create/update), tolerant of shape.
resource_after[[rtype, name, after]] {
	rc := input.resource_changes[_]
	rtype := rc.type
	name := rc.address
	after := rc.change.after
}

# ── Data residency: providers must pin af-south-1 ────────────────────────────
deny[msg] {
	pc := input.configuration.provider_config[_]
	pc.name == "aws"
	region := pc.expressions.region.constant_value
	region != "af-south-1"
	msg := sprintf("Data residency: aws provider region must be 'af-south-1', got '%s' (Vision §5).", [region])
}

# ── No public S3 (ACL) ───────────────────────────────────────────────────────
public_acls := {"public-read", "public-read-write", "website"}

deny[msg] {
	resource_after[[rtype, name, after]]
	rtype == "aws_s3_bucket"
	after.acl in public_acls
	msg := sprintf("Public S3: bucket '%s' has public ACL '%s' — public buckets are forbidden.", [name, after.acl])
}

# ── No public S3 (public access block must stay ON) ──────────────────────────
deny[msg] {
	resource_after[[rtype, name, after]]
	rtype == "aws_s3_bucket_public_access_block"
	some field in ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"]
	after[field] == false
	msg := sprintf("Public S3: '%s' sets %s=false — all four public-access blocks must be true.", [name, field])
}

# ── No wildcard IAM actions/resources ────────────────────────────────────────
iam_policy_types := {"aws_iam_policy", "aws_iam_role_policy", "aws_iam_user_policy", "aws_iam_group_policy"}

deny[msg] {
	resource_after[[rtype, name, after]]
	iam_policy_types[rtype]
	doc := after.policy
	is_string(doc)
	contains(doc, "\"Action\": \"*\"")
	msg := sprintf("Wildcard IAM: '%s' grants Action \"*\" — least-privilege only (Plan §2 G4).", [name])
}

deny[msg] {
	resource_after[[rtype, name, after]]
	iam_policy_types[rtype]
	doc := after.policy
	is_string(doc)
	contains(doc, "\"Resource\": \"*\"")
	msg := sprintf("Wildcard IAM: '%s' grants Resource \"*\" — scope resources explicitly (Plan §2 G4).", [name])
}

# ── No plaintext secrets: SSM params must be SecureString ────────────────────
deny[msg] {
	resource_after[[rtype, name, after]]
	rtype == "aws_ssm_parameter"
	after.type != "SecureString"
	msg := sprintf("Secrets: SSM parameter '%s' is type '%s' — credentials must be SecureString (Plan P0.5 #13).", [name, after.type])
}
