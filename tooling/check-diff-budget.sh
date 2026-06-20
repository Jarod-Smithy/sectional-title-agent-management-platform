#!/usr/bin/env bash
# Diff-size budget (Plan §2 G12). Caps how much a single PR/agent run may change
# so that review and eval stay reliable. A human can override an oversized,
# legitimate change by adding the 'oversized-change-approved' PR label.
#
#   usage: tooling/check-diff-budget.sh <base_ref> [head_ref]
#
# Budgets (override via env): files <= MAX_FILES, added+removed <= MAX_LINES.
set -euo pipefail

BASE_REF="${1:?base ref required (e.g. origin/main or base SHA)}"
HEAD_REF="${2:-HEAD}"

MAX_FILES="${MAX_FILES:-50}"
MAX_LINES="${MAX_LINES:-1500}"

# Lockfiles / generated SBOMs / vendored dirs don't count toward the budget.
EXCLUDES=(
  ':(exclude)**/package-lock.json'
  ':(exclude)**/pnpm-lock.yaml'
  ':(exclude)**/yarn.lock'
  ':(exclude)**/poetry.lock'
  ':(exclude)**/*.lock'
  ':(exclude)**/sbom*.json'
  ':(exclude)node_modules/**'
)

numstat="$(git diff --numstat "$BASE_REF" "$HEAD_REF" -- . "${EXCLUDES[@]}")"

if [ -z "$numstat" ]; then
  echo "▸ No file changes in budgeted paths. OK."
  exit 0
fi

files="$(printf '%s\n' "$numstat" | grep -c . || true)"
lines="$(printf '%s\n' "$numstat" \
  | awk '{ a = ($1 == "-" ? 0 : $1); d = ($2 == "-" ? 0 : $2); sum += a + d } END { print sum + 0 }')"

echo "▸ Diff budget: ${files}/${MAX_FILES} files, ${lines}/${MAX_LINES} lines changed."

status=0
if [ "$files" -gt "$MAX_FILES" ]; then
  echo "✗ Too many files changed (${files} > ${MAX_FILES})."
  status=1
fi
if [ "$lines" -gt "$MAX_LINES" ]; then
  echo "✗ Too many lines changed (${lines} > ${MAX_LINES})."
  status=1
fi

if [ "$status" -ne 0 ]; then
  echo ""
  echo "This change exceeds the agent diff-size budget (Plan §2 G12)."
  echo "Split it into smaller PRs, or a human can add the"
  echo "'oversized-change-approved' label to override."
  exit 1
fi

echo "✓ Within diff-size budget."
