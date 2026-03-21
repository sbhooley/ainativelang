#!/usr/bin/env bash
# Bootstrap AINL inside OpenClaw: optional npm OpenClaw CLI refresh, PyPI install + ainl install-openclaw.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "${OPENCLAW_SKIP_NPM:-}" != "1" ]]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> Ensuring OpenClaw CLI via npm (install -g openclaw@latest)"
    npm install -g openclaw@latest
  else
    echo "install.sh: npm not on PATH; skipped global OpenClaw CLI refresh." >&2
    echo "    Install the OpenClaw CLI per https://openclaw.ai/ (e.g. npm install -g openclaw && openclaw onboard)." >&2
  fi
else
  echo "==> Skipping npm (OPENCLAW_SKIP_NPM=1)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "install.sh: python3 is required on PATH." >&2
  exit 1
fi

echo "==> Upgrading ainl-lang[mcp] via python3 -m pip"
python3 -m pip install --upgrade 'ainl-lang[mcp]'

if ! command -v ainl >/dev/null 2>&1; then
  echo "install.sh: 'ainl' not found on PATH after pip install." >&2
  echo "    Add Python user scripts to PATH (e.g. export PATH=\"\$(python3 -m site --user-base)/bin:\$PATH\")." >&2
  exit 1
fi

echo "==> Running ainl install-openclaw"
exec ainl install-openclaw "$@"
