#!/usr/bin/env bash
# Run ainl-x-promoter.ainl against a local gateway (defaults to dry-run: no X writes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/apollo-x-bot/.env" ]]; then
  # shellcheck source=/dev/null
  set -a && source "$ROOT/apollo-x-bot/.env" && set +a
fi
PY="${PYTHON:-python3}"
GWHOST="${PROMOTER_GATEWAY_HOST:-127.0.0.1}"
GWPORT="${PROMOTER_GATEWAY_PORT:-17301}"

export PROMOTER_DRY_RUN="${PROMOTER_DRY_RUN:-1}"
export PROMOTER_STATE_PATH="${PROMOTER_STATE_PATH:-$ROOT/apollo-x-bot/data/promoter_state.sqlite}"
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
  --bridge-endpoint "promoter.maybe_daily_post=${BASE}/v1/promoter.maybe_daily_post"
