#!/usr/bin/env bash
# Apply branch protection on `main` from .github/branch-protection.json.
# Requires the GitHub CLI (`gh auth login`) with admin on the repo.
#
#   usage: tooling/apply-branch-protection.sh <owner> <repo>
set -euo pipefail

OWNER="${1:?owner required}"
REPO="${2:?repo required}"
CONFIG="$(dirname "$0")/../.github/branch-protection.json"

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required"; exit 1; }

echo "▸ Applying branch protection to ${OWNER}/${REPO}@main…"
# Strip the documentation-only keys (_comment/_note) before sending.
python3 - "$CONFIG" <<'PY' > /tmp/bp.json
import json,sys
def clean(o):
    if isinstance(o,dict): return {k:clean(v) for k,v in o.items() if not k.startswith('_')}
    if isinstance(o,list): return [clean(v) for v in o]
    return o
json.dump(clean(json.load(open(sys.argv[1]))), sys.stdout)
PY

gh api -X PUT "repos/${OWNER}/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input /tmp/bp.json

echo "✅ Branch protection applied. 'All gates' is now a required status check."
