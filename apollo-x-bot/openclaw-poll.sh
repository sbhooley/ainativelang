#!/usr/bin/env bash
# OpenClaw / cron entrypoint: run one poll of ainl-x-promoter.ainl against an already-running gateway.
# The gateway (apollo-x-bot/gateway_server.py) must be supervised separately — this script only invokes `ainl run`.
#
# Optional env file (export vars before cron, or source a file):
#   export APOLLO_PROMOTER_ENV=~/.openclaw/apollo-x-promoter.env
# File contents example:
#   export X_BEARER_TOKEN=...
#   export OPENAI_API_KEY=...
#   export PROMOTER_GATEWAY_URL=http://127.0.0.1:17302
#   export PROMOTER_DRY_RUN=0
#   export PYTHON=/path/to/venv/bin/python
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Local dev: apollo-x-bot/.env (same vars as gateway). Optional second file overrides.
if [[ -f "$BOT_DIR/.env" ]]; then
  # shellcheck source=/dev/null
  set -a && source "$BOT_DIR/.env" && set +a
fi
ENV_FILE="${APOLLO_PROMOTER_ENV:-$HOME/.openclaw/apollo-x-promoter.env}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a && source "$ENV_FILE" && set +a
fi

# Prefer explicit PYTHON override, then common local runtimes.
if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x "/data/.openclaw/workspace/ainativelang/.venv-ainl/bin/python3" ]]; then
  PY="/data/.openclaw/workspace/ainativelang/.venv-ainl/bin/python3"
else
  PY="python3"
fi
GATEWAY="${PROMOTER_GATEWAY_URL:-http://127.0.0.1:17302}"
GATEWAY="${GATEWAY%/}"

export PROMOTER_STATE_PATH="${PROMOTER_STATE_PATH:-$ROOT/apollo-x-bot/data/promoter_state.sqlite}"
# Default: apollo-x-bot/data/promoter_memory.sqlite — backs record_decision / memory.put (override AINL_MEMORY_DB=...). Same DB can host access_aware_memory-style writes if you add them at graph top level.
export AINL_MEMORY_DB="${AINL_MEMORY_DB:-$ROOT/apollo-x-bot/data/promoter_memory.sqlite}"
# Bridge HTTP client timeout (seconds). Default 5s in cli is too low for batched llm.classify via OpenRouter; align with executor payload timeout_s (~120).
HTTP_TIMEOUT_S="${AINL_HTTP_TIMEOUT_S:-120}"

cd "$ROOT"
exec "$PY" -m cli.main run "$ROOT/apollo-x-bot/ainl-x-promoter.ainl" --strict --label _poll \
  --http-timeout-s "$HTTP_TIMEOUT_S" \
  --enable-adapter bridge \
  --enable-adapter api \
  --enable-adapter memory \
  --memory-db "$AINL_MEMORY_DB" \
  --bridge-endpoint "x.search=${GATEWAY}/v1/x.search" \
  --bridge-endpoint "llm.classify=${GATEWAY}/v1/llm.classify" \
  --bridge-endpoint "llm.chat=${GATEWAY}/v1/llm.chat" \
  --bridge-endpoint "llm.json_array_extract=${GATEWAY}/v1/llm.json_array_extract" \
  --bridge-endpoint "llm.merge_classify_rows=${GATEWAY}/v1/llm.merge_classify_rows" \
  --bridge-endpoint "promoter.text_contains_any=${GATEWAY}/v1/promoter.text_contains_any" \
  --bridge-endpoint "promoter.heuristic_scores=${GATEWAY}/v1/promoter.heuristic_scores" \
  --bridge-endpoint "promoter.classify_prompts=${GATEWAY}/v1/promoter.classify_prompts" \
  --bridge-endpoint "promoter.daily_post_prompts=${GATEWAY}/v1/promoter.daily_post_prompts" \
  --bridge-endpoint "promoter.daily_snippets=${GATEWAY}/v1/promoter.daily_snippets" \
  --bridge-endpoint "promoter.gate_eval=${GATEWAY}/v1/promoter.gate_eval" \
  --bridge-endpoint "promoter.process_tweet=${GATEWAY}/v1/promoter.process_tweet" \
  --bridge-endpoint "promoter.discover_tweet_authors=${GATEWAY}/v1/promoter.discover_tweet_authors" \
  --bridge-endpoint "promoter.discovery_candidates_from_tweets=${GATEWAY}/v1/promoter.discovery_candidates_from_tweets" \
  --bridge-endpoint "promoter.discovery_score_users=${GATEWAY}/v1/promoter.discovery_score_users" \
  --bridge-endpoint "promoter.discovery_apply_one=${GATEWAY}/v1/promoter.discovery_apply_one" \
  --bridge-endpoint "promoter.discovery_apply_batch=${GATEWAY}/v1/promoter.discovery_apply_batch" \
  --bridge-endpoint "promoter.search_cursor_commit=${GATEWAY}/v1/promoter.search_cursor_commit" \
  --bridge-endpoint "promoter.maybe_daily_post=${GATEWAY}/v1/promoter.maybe_daily_post" \
  --bridge-endpoint "kv.get=${GATEWAY}/v1/kv.get" \
  --bridge-endpoint "kv.set=${GATEWAY}/v1/kv.set"
