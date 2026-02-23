#!/usr/bin/env bash
set -euo pipefail

echo "==> AINL bootstrap (Unix/macOS)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required (>=3.9)." >&2
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,web]"

echo
echo "Bootstrap complete."
echo "Activate: source .venv/bin/activate"
echo "Validate: ainl-validate examples/blog.lang --emit ir"
