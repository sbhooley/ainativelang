#!/usr/bin/env bash
# Bootstrap AINL inside Hermes Agent: pip install + ainl install-mcp --host hermes + local Hermes skills drop.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DRY_RUN=0
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY_RUN=1
  fi
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "install.sh: python3 is required on PATH." >&2
  exit 1
fi

if [[ "${AINL_HERMES_INSTALL_MCP_ALREADY:-}" != "1" ]]; then
  echo "==> Upgrading ainl[mcp] via python3 -m pip"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] would run: python3 -m pip install --upgrade 'ainativelang[mcp]'"
  else
    python3 -m pip install --upgrade 'ainativelang[mcp]'
  fi

  if ! command -v ainl >/dev/null 2>&1; then
    echo "install.sh: 'ainl' not found on PATH after pip install." >&2
    echo "    Add Python user scripts to PATH (e.g. export PATH=\"\$(python3 -m site --user-base)/bin:\$PATH\")." >&2
    exit 1
  fi

  echo "==> Running ainl install-mcp --host hermes"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] would run: ainl install-mcp --host hermes $*"
  else
    ainl install-mcp --host hermes "$@"
  fi
else
  echo "==> Skipping ainl install-mcp (already running under installer hook)"
fi

HERMES_ROOT="${HERMES_ROOT:-$HOME/.hermes}"
SKILLS_DIR="${HERMES_SKILLS_DIR:-$HERMES_ROOT/skills}"
TARGET_DIR="$SKILLS_DIR/ainl"

echo "==> Installing Hermes skills into: $TARGET_DIR"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] would mkdir -p \"$TARGET_DIR\""
else
  mkdir -p "$TARGET_DIR"
fi

copy_one() {
  local src="$1"
  local dst="$2"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] would copy: $src -> $dst"
    return 0
  fi
  cp -f "$src" "$dst"
}

copy_one "$ROOT/SKILL.md" "$TARGET_DIR/SKILL.md"
copy_one "$ROOT/README.md" "$TARGET_DIR/README.md"
copy_one "$ROOT/ainl_hermes_bridge.py" "$TARGET_DIR/ainl_hermes_bridge.py"
copy_one "$ROOT/example_ainl_to_hermes_skill.ainl" "$TARGET_DIR/example_ainl_to_hermes_skill.ainl"

echo
echo "AINL Hermes skill pack installed."
echo "Next:"
echo "  - Start Hermes: hermes chat"
echo "  - Say: \"Import the morning briefing using AINL\""
echo "If hermes is not on PATH yet, install Hermes Agent first and ensure ~/.hermes/bin is on PATH."

