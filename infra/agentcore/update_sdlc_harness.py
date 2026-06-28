#!/usr/bin/env python3
"""Apply the STAK SDLC harness configuration (system prompt + limits).

AgentCore harnesses have no Terraform provider yet, so this script is the
version-controlled source of truth for the harness's mutable config. It reads
the prompt from ``sdlc-harness-system-prompt.txt`` (sibling file) and calls
``bedrock-agentcore-control:UpdateHarness`` via the AWS CLI (portable across
boto3 versions) to push it.

Usage (needs valid AWS creds for profile stak_aws_dev / account 596451157763):
    AWS_PROFILE=stak_aws_dev python3 infra/agentcore/update_sdlc_harness.py

Idempotent: re-running with an unchanged prompt is a harmless no-op update.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import tempfile

HARNESS_ID = "stak_sdlc_agent-SoN87gqXRC"
REGION = "eu-west-1"
# Iteration budget: the previous value (50) was exhausted during diagnosis
# before the agent reached the commit/PR step, so give it headroom while
# staying under the trigger worker Lambda's 900s timeout.
MAX_ITERATIONS = 90

_PROMPT_FILE = pathlib.Path(__file__).with_name("sdlc-harness-system-prompt.txt")


def main() -> None:
    prompt = _PROMPT_FILE.read_text(encoding="utf-8").strip()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump([{"text": prompt}], fh)
        prompt_path = fh.name

    subprocess.run(  # noqa: S603 - trusted ops script, fixed args only
        [
            shutil.which("aws") or "aws",
            "bedrock-agentcore-control",
            "update-harness",
            "--harness-id",
            HARNESS_ID,
            "--region",
            REGION,
            "--system-prompt",
            f"file://{prompt_path}",
            "--max-iterations",
            str(MAX_ITERATIONS),
            "--no-cli-pager",
        ],
        check=True,
    )
    print(f"updated harness {HARNESS_ID} (max-iterations={MAX_ITERATIONS})")


if __name__ == "__main__":
    main()
