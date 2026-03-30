#!/usr/bin/env bash
# Start/restart the apollo-x gateway. Safe to call multiple times — kills existing instance first.
set -euo pipefail

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$BOT_DIR/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv-ainl/bin/python3}"
PIDFILE="/tmp/ainl-gateway.pid"
LOGFILE="/tmp/ainl-gateway.log"

if [[ -f "$BOT_DIR/.env" ]]; then
  set -a && source "$BOT_DIR/.env" && set +a
fi

if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Stopping existing gateway (PID $OLD_PID)..."
    kill "$OLD_PID" && sleep 1
  fi
  rm -f "$PIDFILE"
fi

cd "$ROOT"
nohup "$PY" apollo-x-bot/gateway_server.py >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "Gateway started (PID $!), logging to $LOGFILE"
sleep 2
# Health check
if kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
  echo "Gateway is running."
else
  echo "ERROR: Gateway failed to start. Check $LOGFILE"
  exit 1
fi
