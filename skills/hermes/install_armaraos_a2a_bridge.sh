#!/usr/bin/env bash
# Install ArmaraOS-shaped A2A bridge into ~/.hermes (AINL skill pack).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/armaraos-a2a-bridge"
HERMES_ROOT="${HERMES_ROOT:-$HOME/.hermes}"
TARGET="$HERMES_ROOT/skills/ainl/armaraos-a2a-bridge"
PORT="${HERMES_AINL_BRIDGE_PORT:-18765}"
DRY_RUN=0
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY_RUN=1
  fi
done

if [[ ! -f "$SRC/armaraos_a2a_bridge.py" ]]; then
  echo "install_armaraos_a2a_bridge.sh: missing $SRC/armaraos_a2a_bridge.py" >&2
  exit 1
fi

echo "==> Installing ArmaraOS A2A bridge into: $TARGET"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] mkdir -p \"$TARGET\""
else
  mkdir -p "$TARGET"
  cp -f "$SRC/armaraos_a2a_bridge.py" "$TARGET/armaraos_a2a_bridge.py"
  cp -f "$SRC/hermes_chat_delegate.py" "$TARGET/hermes_chat_delegate.py"
  cp -f "$SRC/README.md" "$TARGET/README.md"
  if [[ -f "$SRC/smoke_test_a2a_bridge.sh" ]]; then
    cp -f "$SRC/smoke_test_a2a_bridge.sh" "$TARGET/smoke_test_a2a_bridge.sh"
    chmod +x "$TARGET/smoke_test_a2a_bridge.sh"
  fi
fi

LAUNCH="$TARGET/run-bridge.sh"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] would write $LAUNCH"
else
  cat >"$LAUNCH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export HERMES_AINL_BRIDGE_PORT="\${HERMES_AINL_BRIDGE_PORT:-$PORT}"
exec python3 "\$(dirname "\$0")/armaraos_a2a_bridge.py" "\$@"
EOF
  chmod +x "$LAUNCH"
fi

A2A_JSON="$HERMES_ROOT/a2a.json"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] would write $A2A_JSON"
else
  mkdir -p "$HERMES_ROOT"
  cat >"$A2A_JSON" <<EOF
{
  "base_url": "http://127.0.0.1:$PORT",
  "send_binding": "auto"
}
EOF
fi

echo
echo "Installed. Next:"
echo "  1) (Optional) export HERMES_AINL_BRIDGE_CMD='…'  # stdin/stdout delegate to Hermes"
echo "  2) Run:  $LAUNCH"
echo "  3) In ArmaraOS: hermes_a2a_status  →  a2a_send_hermes with your task"
echo
echo "a2a.json written: $A2A_JSON"
