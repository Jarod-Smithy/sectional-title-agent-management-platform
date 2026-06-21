#!/usr/bin/env bash
# Run the local prototype. No dependencies — pure Python standard library.
set -euo pipefail
cd "$(dirname "$0")"

PY="$(command -v python3 || command -v python)"
echo "▸ Starting on http://localhost:${PORT:-8000}  (Ctrl-C to stop)"
exec "$PY" -m app.main
