#!/usr/bin/env bash
# Bootstrap AINL inside ZeroClaw: PyPI install + ainl install-mcp --host zeroclaw (MCP + shim).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

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

echo "==> Running ainl install-mcp --host zeroclaw"
exec ainl install-mcp --host zeroclaw "$@"
