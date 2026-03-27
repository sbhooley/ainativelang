#!/usr/bin/env bash
# Bootstrap AINL for restricted environments (PEP 668 safe) + MCP host setup.
set -euo pipefail

echo "AINL skill installer (PEP 668 / restricted env aware)"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "install.sh: ${PYTHON} is required on PATH." >&2
  exit 1
fi

install_ainl() {
  echo "Installing ainl[mcp]..."
  PIP_BASE=("$PYTHON" -m pip install --upgrade --no-input "ainativelang[mcp]")

  if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "Detected active virtualenv: $VIRTUAL_ENV"
  else
    echo "No active virtualenv detected; trying no-root fallback install modes as needed."
  fi

  if "${PIP_BASE[@]}"; then
    echo "Installed with default pip"
    return 0
  fi

  if "${PIP_BASE[@]}" --user 2>/dev/null; then
    echo "Installed with --user (PEP 668 fallback)"
    ensure_path_line 'export PATH="$HOME/.local/bin:$PATH"'
    return 0
  fi

  if "${PIP_BASE[@]}" --break-system-packages 2>/dev/null; then
    echo "Installed with --break-system-packages (PEP 668 fallback)"
    return 0
  fi

  echo "All install methods failed. This sandbox may require manual venv/platform install." >&2
  return 1
}

ensure_path_line() {
  local line="$1"
  local marker="${line#export PATH=\"\$HOME/}"
  marker="${marker%%:*}"
  local rc
  for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    [ -f "$rc" ] || continue
    if grep -Fq "$marker" "$rc" 2>/dev/null; then
      continue
    fi
    printf "\n# Added by AINL skill installer\n%s\n" "$line" >> "$rc" 2>/dev/null || true
  done
}

install_ainl

if ! command -v ainl >/dev/null 2>&1; then
  USER_BIN="$($PYTHON -m site --user-base 2>/dev/null)/bin"
  if [ -x "$USER_BIN/ainl" ]; then
    export PATH="$USER_BIN:$PATH"
  fi
fi

if ! command -v ainl >/dev/null 2>&1; then
  echo "install.sh: 'ainl' still not found on PATH after install." >&2
  echo "Add Python user scripts to PATH: export PATH=\"\$($PYTHON -m site --user-base)/bin:\$PATH\"" >&2
  exit 1
fi

echo "Setting up MCP for OpenClaw/ZeroClaw host..."
ainl install-mcp --host openclaw "$@" || ainl install-mcp --host zeroclaw "$@"

echo "AINL skill fully installed and MCP registered."
