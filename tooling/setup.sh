#!/usr/bin/env bash
# One-time developer setup for the AI-native SDLC.
# Installs pre-commit and wires the git hooks (pre-commit + commit-msg).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "▸ Checking prerequisites…"
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v git >/dev/null || { echo "git is required"; exit 1; }

echo "▸ Installing pre-commit (user scope)…"
if ! command -v pre-commit >/dev/null; then
  python3 -m pip install --user pre-commit
fi

echo "▸ Installing git hooks…"
pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg

echo "▸ Running hooks once across the repo (first run downloads tool environments)…"
pre-commit run --all-files || {
  echo "⚠ Some hooks made fixes or found issues. Review, stage, and re-run.";
}

echo "✅ Setup complete. Hooks will now run on every commit."
echo "   Tip: 'pre-commit run --all-files' to check everything on demand."
