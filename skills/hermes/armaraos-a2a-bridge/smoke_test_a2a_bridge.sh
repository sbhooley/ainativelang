#!/usr/bin/env bash
# End-to-end: temp ~/.hermes layout + bridge + AINL A2aAdapter discover_hermes/send_hermes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../../.." && pwd)"
PORT="${TEST_BRIDGE_PORT:-$(python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()')}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/hermes-a2a-smoke.XXXXXX")"
cleanup() {
  if [[ -n "${BRIDGE_PID:-}" ]] && kill -0 "${BRIDGE_PID}" 2>/dev/null; then
    kill "${BRIDGE_PID}" 2>/dev/null || true
    wait "${BRIDGE_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP}"
}
trap cleanup EXIT

HERMES_BIN="${HERMES_BIN:-$(command -v hermes || true)}"
if [[ -z "${HERMES_BIN}" ]]; then
  echo "smoke_test: hermes not on PATH; set HERMES_BIN" >&2
  exit 2
fi

mkdir -p "${TMP}"
cat >"${TMP}/a2a.json" <<EOF
{"base_url": "http://127.0.0.1:${PORT}", "send_binding": "auto"}
EOF

export HERMES_AINL_BRIDGE_HOST="${HERMES_AINL_BRIDGE_HOST:-127.0.0.1}"
export HERMES_AINL_BRIDGE_PORT="${PORT}"
export HERMES_AINL_BRIDGE_QUIET="${HERMES_AINL_BRIDGE_QUIET:-1}"
export HERMES_BIN
export HERMES_AINL_BRIDGE_CMD="python3 ${ROOT}/hermes_chat_delegate.py"

python3 "${ROOT}/armaraos_a2a_bridge.py" &
BRIDGE_PID=$!
sleep 1

if ! kill -0 "${BRIDGE_PID}" 2>/dev/null; then
  echo "smoke_test: bridge failed to start" >&2
  exit 3
fi

python3 <<PY
import json
import sys
from pathlib import Path

sys.path.insert(0, "${REPO_ROOT}")
from runtime.adapters.a2a import A2aAdapter

root = Path("${TMP}")
ad = A2aAdapter(allow_insecure_local=True, default_timeout_s=120.0, max_response_bytes=2_000_000)
ctx: dict = {}
card = ad.call("discover_hermes", [str(root)], ctx)
assert isinstance(card, dict), card
assert card.get("name") or card.get("url"), card

msg = "Reply with exactly one word: PONG"
res = ad.call("send_hermes", [msg, None, 120.0, str(root)], ctx)
text = json.dumps(res, ensure_ascii=False)
print("send_hermes_ok", len(text))
if "PONG" not in text.upper():
    print(text[:2000], file=sys.stderr)
    sys.exit(4)
PY

echo "smoke_test_a2a_bridge: OK (port ${PORT})"
