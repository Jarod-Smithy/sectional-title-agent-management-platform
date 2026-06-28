"""GitHub webhook -> Amazon Bedrock AgentCore SDLC harness trigger.

API Gateway invokes this Lambda on a GitHub ``issues`` webhook. The function:

1. Verifies the GitHub HMAC-SHA256 signature (``X-Hub-Signature-256``) against a
   shared secret held in Secrets Manager.
2. When an issue is labelled ``ai-sdlc`` (action labeled/opened/reopened), it
   asynchronously self-invokes (``InvocationType=Event``) so it can ACK GitHub
   within the webhook timeout, and the async copy runs the harness.
3. The async ``_worker`` path calls ``bedrock-agentcore:InvokeHarness`` with the
   issue as the user message and drains the response stream.

Only ``boto3`` is used (present in the Lambda runtime) — no extra dependencies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

HARNESS_ARN = os.environ["HARNESS_ARN"]
WEBHOOK_SECRET_NAME = os.environ["WEBHOOK_SECRET_NAME"]
SELF_FUNCTION_NAME = os.environ["SELF_FUNCTION_NAME"]
TRIGGER_LABEL = os.environ.get("TRIGGER_LABEL", "ai-sdlc")
# Dedup: GitHub fires opened+labeled (and reopened) for the same issue within
# seconds, which would race two agent runs. A conditional PutItem keyed by issue
# number lets only the first event in this window dispatch the worker. Short
# enough that a deliberate manual re-trigger still works after a minute or two.
DEDUP_TABLE = os.environ.get("DEDUP_TABLE", "")
_DEDUP_TTL_SECONDS = 180
# Bedrock can throttle the harness's ConverseStream under load (e.g. when GitHub
# fires opened+labeled and two runs race). Retry the whole run a few times with
# exponential backoff so a transient ThrottlingException doesn't drop the issue.
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 20

_secrets = boto3.client("secretsmanager")
_lambda = boto3.client("lambda")
_dynamodb = boto3.client("dynamodb")
# The harness streams for minutes; keep the socket open well within the Lambda's
# 15-minute ceiling and disable retries (a partial stream must not be replayed).
_agent = boto3.client(
    "bedrock-agentcore",
    config=Config(read_timeout=870, connect_timeout=10, retries={"max_attempts": 0}),
)


def _webhook_secret() -> bytes:
    return _secrets.get_secret_value(SecretId=WEBHOOK_SECRET_NAME)["SecretString"].strip().encode()


def _ack(status: int, message: str) -> dict[str, Any]:
    return {"statusCode": status, "body": json.dumps({"message": message})}


def _claim_issue(number: Any) -> bool:
    """Win the dispatch race for an issue. True = this event should dispatch.

    Conditional PutItem: succeeds only when no live claim exists (or the prior
    claim's TTL has logically passed — DynamoDB's physical TTL sweep can lag).
    Fail-open: if the table is unset or DynamoDB errors, allow the dispatch.
    """
    if not DEDUP_TABLE or number is None:
        return True
    now = int(time.time())
    try:
        _dynamodb.put_item(
            TableName=DEDUP_TABLE,
            Item={"issue": {"S": str(number)}, "expires_at": {"N": str(now + _DEDUP_TTL_SECONDS)}},
            ConditionExpression="attribute_not_exists(issue) OR expires_at < :now",
            ExpressionAttributeValues={":now": {"N": str(now)}},
        )
        return True
    except _dynamodb.exceptions.ConditionalCheckFailedException:
        return False
    except (ClientError, BotoCoreError):
        return True


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Async worker path: actually run the agent (can take minutes).
    if event.get("_worker"):
        return _run_agent(event["issue"])

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    signature = headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(_webhook_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return _ack(401, "invalid signature")

    if headers.get("x-github-event") != "issues":
        return _ack(204, "ignored (not an issues event)")
    payload = json.loads(body or "{}")
    if payload.get("action") not in ("labeled", "opened", "reopened"):
        return _ack(204, "ignored (action not actionable)")
    issue = payload.get("issue") or {}
    labels = [label.get("name") for label in issue.get("labels", [])]
    if TRIGGER_LABEL not in labels:
        return _ack(204, f"ignored (no '{TRIGGER_LABEL}' label)")

    # Collapse GitHub's opened+labeled double-fire: only the first event wins.
    if not _claim_issue(issue.get("number")):
        return _ack(202, f"deduplicated issue #{issue.get('number')} (already dispatched)")

    _lambda.invoke(
        FunctionName=SELF_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps(
            {
                "_worker": True,
                "issue": {
                    "number": issue.get("number"),
                    "title": issue.get("title") or "",
                    "body": issue.get("body") or "",
                    "labels": labels,
                },
            }
        ).encode(),
    )
    return _ack(202, f"dispatched issue #{issue.get('number')} to the SDLC agent")


def _is_throttle(text: str | None) -> bool:
    low = (text or "").lower()
    return "throttl" in low or "too many requests" in low or "max retries" in low


def _run_agent(issue: dict[str, Any]) -> dict[str, Any]:
    message = (
        f"GitHub issue #{issue['number']} (labels: {', '.join(issue['labels'])}).\n"
        f"Title: {issue['title']}\n\n{issue['body']}"
    )
    last_error = "unknown error"
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = _agent.invoke_harness(
                harnessArn=HARNESS_ARN,
                runtimeSessionId=f"ai-sdlc-issue-{issue['number']}-{uuid.uuid4().hex}",
                messages=[{"role": "user", "content": [{"text": message}]}],
            )
            stop_reason = "unknown"
            for chunk in response["stream"]:
                if "messageStop" in chunk:
                    stop_reason = chunk["messageStop"].get("stopReason", stop_reason)
                elif "runtimeClientError" in chunk:
                    last_error = chunk["runtimeClientError"].get("message", "runtime error")
                    if _is_throttle(last_error) and attempt + 1 < _MAX_ATTEMPTS:
                        break  # fall through to backoff + retry
                    return {"ok": False, "issue": issue["number"], "error": last_error}
            else:
                return {"ok": True, "issue": issue["number"], "stopReason": stop_reason}
        except (ClientError, BotoCoreError) as exc:
            last_error = str(exc)
            if not (_is_throttle(last_error) and attempt + 1 < _MAX_ATTEMPTS):
                return {"ok": False, "issue": issue["number"], "error": last_error}
        time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
    return {"ok": False, "issue": issue["number"], "error": last_error}
