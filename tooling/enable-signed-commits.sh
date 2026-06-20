#!/usr/bin/env bash
# Enable required commit signing on `main` (Plan §2 G1 / P0 #7).
#
# Branch protection's main payload does NOT accept a signatures key; it lives on
# a separate endpoint. This script toggles it on. Pair it with gitsign so agents
# (and humans) sign commits keylessly via Sigstore/OIDC — no GPG keys to manage.
#
#   usage: tooling/enable-signed-commits.sh <owner> <repo>
#
# Developer setup for keyless signing (gitsign):
#   brew install sigstore/tap/gitsign        # or: go install github.com/sigstore/gitsign@latest
#   git config --global commit.gpgsign true
#   git config --global tag.gpgsign true
#   git config --global gpg.x509.program gitsign
#   git config --global gpg.format x509
set -euo pipefail

OWNER="${1:?owner required}"
REPO="${2:?repo required}"

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required"; exit 1; }

echo "▸ Enabling required signed commits on ${OWNER}/${REPO}@main…"
gh api -X POST "repos/${OWNER}/${REPO}/branches/main/protection/required_signatures" \
  -H "Accept: application/vnd.github+json"

echo "✅ Signed commits now required on main."
echo "   Contributors must configure gitsign (see header) or commits will be rejected."
