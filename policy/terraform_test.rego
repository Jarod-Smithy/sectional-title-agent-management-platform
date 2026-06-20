# Tests for policy/terraform.rego. Run: conftest verify --policy policy/
package main

import future.keywords.in

# ── Region ───────────────────────────────────────────────────────────────────
test_denies_wrong_region {
	deny[_] with input as {"configuration": {"provider_config": {"aws": {
		"name": "aws",
		"expressions": {"region": {"constant_value": "us-east-1"}},
	}}}}
}

test_allows_af_south_1 {
	count(deny) == 0 with input as {"configuration": {"provider_config": {"aws": {
		"name": "aws",
		"expressions": {"region": {"constant_value": "af-south-1"}},
	}}}}
}

# ── Public S3 ────────────────────────────────────────────────────────────────
test_denies_public_acl {
	deny[_] with input as {"resource_changes": [{
		"type": "aws_s3_bucket",
		"address": "aws_s3_bucket.docs",
		"change": {"after": {"acl": "public-read"}},
	}]}
}

test_denies_disabled_public_access_block {
	deny[_] with input as {"resource_changes": [{
		"type": "aws_s3_bucket_public_access_block",
		"address": "aws_s3_bucket_public_access_block.docs",
		"change": {"after": {"block_public_acls": false}},
	}]}
}

# ── Wildcard IAM ─────────────────────────────────────────────────────────────
test_denies_wildcard_action {
	deny[_] with input as {"resource_changes": [{
		"type": "aws_iam_policy",
		"address": "aws_iam_policy.broad",
		"change": {"after": {"policy": "{\"Statement\":[{\"Action\": \"*\",\"Resource\": \"arn:aws:s3:::b\"}]}"}},
	}]}
}

# ── SSM SecureString ─────────────────────────────────────────────────────────
test_denies_plaintext_ssm {
	deny[_] with input as {"resource_changes": [{
		"type": "aws_ssm_parameter",
		"address": "aws_ssm_parameter.token",
		"change": {"after": {"type": "String"}},
	}]}
}

test_allows_securestring_ssm {
	count(deny) == 0 with input as {"resource_changes": [{
		"type": "aws_ssm_parameter",
		"address": "aws_ssm_parameter.token",
		"change": {"after": {"type": "SecureString"}},
	}]}
}
