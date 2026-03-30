#!/usr/bin/env bash
# Resolve a Python that matches the project baseline (prefer .venv-py310, .venv-ainl, then .venv).
# Used by pre-commit so `python` on PATH is not required.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

_candidates=()
if [[ -n "${AINL_PYTHON:-}" ]]; then
  _candidates+=("${AINL_PYTHON}")
fi
_candidates+=("${ROOT}/.venv-py310/bin/python")
_candidates+=("${ROOT}/.venv-ainl/bin/python")
_candidates+=("${ROOT}/.venv/bin/python")
if command -v python3 >/dev/null 2>&1; then
  _candidates+=("$(command -v python3)")
fi

_py=""
for c in "${_candidates[@]}"; do
  [[ -z "${c}" ]] && continue
  if [[ -x "${c}" ]]; then
    _py="${c}"
    break
  fi
done

if [[ -z "${_py}" ]]; then
  echo "precommit_docs_contract: no Python found. Create .venv-py310 (see docs/INSTALL.md) or set AINL_PYTHON." >&2
  exit 1
fi

exec "${_py}" "${ROOT}/scripts/check_docs_contracts.py" --scope changed
