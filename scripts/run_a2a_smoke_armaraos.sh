#!/usr/bin/env bash
# Run A2A smoke against local ArmaraOS (openfang-api on loopback).
# Optional: A2A_SMOKE_BASE=http://127.0.0.1:PORT (no trailing slash)
# If unset, uses the first openfang TCP listen on 127.0.0.1 (lsof).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${A2A_SMOKE_BASE:-}" ]]; then
  base="${A2A_SMOKE_BASE%/}"
else
  line=$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E 'openfang|OpenFang' | grep '127.0.0.1' | head -1 || true)
  if [[ -z "${line}" ]]; then
    echo "run_a2a_smoke_armaraos: no openfang listener; set A2A_SMOKE_BASE=http://127.0.0.1:PORT" >&2
    exit 1
  fi
  addr=$(echo "$line" | awk '{
    for (i = 1; i <= NF; i++) {
      if ($i ~ /^127\.0\.0\.1:[0-9]+$/) { print $i; exit }
    }
  }')
  if [[ -z "$addr" || ! "$addr" =~ ^127\.0\.0\.1:[0-9]+$ ]]; then
    echo "run_a2a_smoke_armaraos: could not parse 127.0.0.1:PORT from: $line" >&2
    exit 1
  fi
  base="http://${addr}"
fi

port="${base##*:}"
src="$ROOT/examples/compact/a2a_smoke_local.ainl"
tmp="$(mktemp -t a2a_smoke.ainl.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

# Replace default port 57219 with detected port in literal URLs
sed -e "s/127.0.0.1:57219/127.0.0.1:${port}/g" "$src" > "$tmp"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

exec "$PYTHON" -m cli.main run "$tmp" --json \
  --enable-adapter a2a \
  --a2a-allow-host 127.0.0.1 \
  --a2a-allow-insecure-local \
  --a2a-timeout-s 120 \
  "$@"
