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
fi
# If not set by caller or .env, default to dry-run for safety
if [ -z "${PROMOTER_DRY_RUN+set}" ]; then
  export PROMOTER_DRY_RUN=1
fi
PY="${PYTHON:-python3}"
# Ensure Python can find the cli module in the repo root
if [ -z "${PYTHONPATH+set}" ]; then
  export PYTHONPATH="$ROOT"
else
  export PYTHONPATH="$ROOT:$PYTHONPATH"
fi
GWHOST="${PROMOTER_GATEWAY_HOST:-127.0.0.1}"
GWPORT="${PROMOTER_GATEWAY_PORT:-17302}"
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
HTTP_TIMEOUT_S="${AINL_HTTP_TIMEOUT_S:-120}"
"$PY" -m cli.main run "$ROOT/apollo-x-bot/ainl-x-promoter.ainl" --strict --label _poll \
  --http-timeout-s "$HTTP_TIMEOUT_S" \
  --enable-adapter bridge \
  --enable-adapter api \
  --enable-adapter memory \
  --memory-db "$AINL_MEMORY_DB" \
  --bridge-endpoint "x.search=${BASE}/v1/x.search" \
  --bridge-endpoint "llm.classify=${BASE}/v1/llm.classify" \
  --bridge-endpoint "llm.chat=${BASE}/v1/llm.chat" \
  --bridge-endpoint "llm.json_array_extract=${BASE}/v1/llm.json_array_extract" \
  --bridge-endpoint "llm.merge_classify_rows=${BASE}/v1/llm.merge_classify_rows" \
  --bridge-endpoint "promoter.text_contains_any=${BASE}/v1/promoter.text_contains_any" \
  --bridge-endpoint "promoter.heuristic_scores=${BASE}/v1/promoter.heuristic_scores" \
  --bridge-endpoint "promoter.classify_prompts=${BASE}/v1/promoter.classify_prompts" \
  --bridge-endpoint "promoter.daily_post_prompts=${BASE}/v1/promoter.daily_post_prompts" \
  --bridge-endpoint "promoter.daily_snippets=${BASE}/v1/promoter.daily_snippets" \
  --bridge-endpoint "promoter.gate_eval=${BASE}/v1/promoter.gate_eval" \
  --bridge-endpoint "promoter.process_tweet=${BASE}/v1/promoter.process_tweet" \
  --bridge-endpoint "promoter.discover_tweet_authors=${BASE}/v1/promoter.discover_tweet_authors" \
  --bridge-endpoint "promoter.discovery_candidates_from_tweets=${BASE}/v1/promoter.discovery_candidates_from_tweets" \
  --bridge-endpoint "promoter.discovery_score_users=${BASE}/v1/promoter.discovery_score_users" \
  --bridge-endpoint "promoter.discovery_apply_one=${BASE}/v1/promoter.discovery_apply_one" \
  --bridge-endpoint "promoter.discovery_apply_batch=${BASE}/v1/promoter.discovery_apply_batch" \
  --bridge-endpoint "promoter.search_cursor_commit=${BASE}/v1/promoter.search_cursor_commit" \
  --bridge-endpoint "promoter.maybe_daily_post=${BASE}/v1/promoter.maybe_daily_post" \
  --bridge-endpoint "kv.get=${BASE}/v1/kv.get" \
  --bridge-endpoint "kv.set=${BASE}/v1/kv.set"
