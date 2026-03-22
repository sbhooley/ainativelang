#!/usr/bin/env bash
# Run ainl-x-promoter.ainl against a local gateway (defaults to dry-run: no X writes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# If the caller already set host/port/dry-run, do not let dotenv override.
_port_was_set=0
_host_was_set=0
_dry_was_set=0
# Bash 3.2–compatible: treat "set in environment" as caller override (even empty).
[[ -n "${PROMOTER_GATEWAY_PORT+set}" ]] && _port_was_set=1 && _saved_gw_port="$PROMOTER_GATEWAY_PORT"
[[ -n "${PROMOTER_GATEWAY_HOST+set}" ]] && _host_was_set=1 && _saved_gw_host="$PROMOTER_GATEWAY_HOST"
[[ -n "${PROMOTER_DRY_RUN+set}" ]] && _dry_was_set=1 && _saved_dry="$PROMOTER_DRY_RUN"
if [[ -f "$ROOT/apollo-x-bot/.env" ]]; then
  # shellcheck source=/dev/null
  set -a && source "$ROOT/apollo-x-bot/.env" && set +a
fi
[[ "$_port_was_set" -eq 1 ]] && export PROMOTER_GATEWAY_PORT="$_saved_gw_port"
[[ "$_host_was_set" -eq 1 ]] && export PROMOTER_GATEWAY_HOST="$_saved_gw_host"
if [[ "$_dry_was_set" -eq 1 ]]; then
  export PROMOTER_DRY_RUN="$_saved_dry"
else
  # This script defaults to dry-run even when .env sets PROMOTER_DRY_RUN=0.
  export PROMOTER_DRY_RUN=1
fi
PY="${PYTHON:-python3}"
GWHOST="${PROMOTER_GATEWAY_HOST:-127.0.0.1}"
GWPORT="${PROMOTER_GATEWAY_PORT:-17301}"
export PROMOTER_STATE_PATH="${PROMOTER_STATE_PATH:-$ROOT/apollo-x-bot/data/promoter_state.sqlite}"
# AINL memory adapter SQLite: record_decision.ainl (and any top-level memory.put). Optional access_aware_memory.ainl patterns also use this DB when wired from a graph.
export AINL_MEMORY_DB="${AINL_MEMORY_DB:-$ROOT/apollo-x-bot/data/promoter_memory.sqlite}"
export PROMOTER_GATEWAY_HOST="${GWHOST}"
export PROMOTER_GATEWAY_PORT="${GWPORT}"

"$PY" "$ROOT/apollo-x-bot/gateway_server.py" &
GW_PID=$!
cleanup() { kill "$GW_PID" 2>/dev/null || true; }
trap cleanup EXIT
sleep 0.5

BASE="http://${GWHOST}:${GWPORT}"
"$PY" -m cli.main run "$ROOT/apollo-x-bot/ainl-x-promoter.ainl" --strict --label _poll \
  --enable-adapter bridge \
  --enable-adapter memory \
  --memory-db "$AINL_MEMORY_DB" \
  --bridge-endpoint "x.search=${BASE}/v1/x.search" \
  --bridge-endpoint "llm.classify=${BASE}/v1/llm.classify" \
  --bridge-endpoint "llm.json_array_extract=${BASE}/v1/llm.json_array_extract" \
  --bridge-endpoint "llm.merge_classify_rows=${BASE}/v1/llm.merge_classify_rows" \
  --bridge-endpoint "promoter.text_contains_any=${BASE}/v1/promoter.text_contains_any" \
  --bridge-endpoint "promoter.heuristic_scores=${BASE}/v1/promoter.heuristic_scores" \
  --bridge-endpoint "promoter.classify_prompts=${BASE}/v1/promoter.classify_prompts" \
  --bridge-endpoint "promoter.gate_eval=${BASE}/v1/promoter.gate_eval" \
  --bridge-endpoint "promoter.process_tweet=${BASE}/v1/promoter.process_tweet" \
  --bridge-endpoint "promoter.search_cursor_commit=${BASE}/v1/promoter.search_cursor_commit" \
  --bridge-endpoint "promoter.maybe_daily_post=${BASE}/v1/promoter.maybe_daily_post" \
  --bridge-endpoint "kv.get=${BASE}/v1/kv.get" \
  --bridge-endpoint "kv.set=${BASE}/v1/kv.set"
