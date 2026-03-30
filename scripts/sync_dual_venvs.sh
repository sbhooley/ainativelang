#!/usr/bin/env bash
# Create or refresh BOTH .venv-py310 (CI-style name) and .venv-ainl (OpenClaw-style name)
# with the same editable install so either interpreter can run pytest, MCP, and host tools.
#
# Usage:
#   bash scripts/sync_dual_venvs.sh
#   PYTHON_BIN=python3.10 AINL_PIP_EXTRAS=dev,web,mcp bash scripts/sync_dual_venvs.sh
#
# Default extras: dev,web,mcp — superset of GitHub Actions (.[dev]) plus web + MCP for OpenClaw.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
EXTRAS="${AINL_PIP_EXTRAS:-dev,web,mcp}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "${PYTHON_BIN} is required (>=3.10). Install Python 3.10+ or set PYTHON_BIN." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "${PYTHON_BIN} must be Python 3.10 or newer (project minimum)." >&2
  exit 1
fi

_sync_one() {
  local dir="$1"
  echo "==> Syncing ${dir} with .[${EXTRAS}]"
  if [[ ! -f "${dir}/bin/activate" ]]; then
    "${PYTHON_BIN}" -m venv "${dir}"
  else
    # Warn if existing env was built with a different minor than PYTHON_BIN (CI is 3.10).
    local cur
    cur="$("${dir}/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    local want
    want="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    if [[ "${cur}" != "${want}" ]]; then
      echo "WARN: ${dir} uses Python ${cur} but PYTHON_BIN is ${want}. Remove ${dir} and re-run to match CI, or keep for experiments." >&2
    fi
  fi
  # shellcheck source=/dev/null
  source "${dir}/bin/activate"
  python -m pip install --upgrade pip
  pip install -U -e ".[${EXTRAS}]"
  deactivate
}

_sync_one ".venv-py310"
_sync_one ".venv-ainl"

echo ""
echo "Dual venv sync complete. Use either:"
echo "  ./.venv-py310/bin/python   (CI / docs convention)"
echo "  ./.venv-ainl/bin/python    (OpenClaw / cron scripts)"
echo "Extras: [${EXTRAS}] — override with AINL_PIP_EXTRAS=..."
