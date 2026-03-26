#!/usr/bin/env bash
# Optional: thread fetch + promoter.thread_continue (thread_engagement.ainl). Set PROMOTER_THREAD_ENABLED=1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$BOT_DIR/.env" ]]; then
  set -a && source "$BOT_DIR/.env" && set +a
fi
ENV_FILE="${APOLLO_PROMOTER_ENV:-$HOME/.openclaw/apollo-x-promoter.env}"
if [[ -f "$ENV_FILE" ]]; then
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
HTTP_TIMEOUT_S="${AINL_HTTP_TIMEOUT_S:-120}"

export PROMOTER_STATE_PATH="${PROMOTER_STATE_PATH:-$ROOT/apollo-x-bot/data/promoter_state.sqlite}"
export AINL_MEMORY_DB="${AINL_MEMORY_DB:-$ROOT/apollo-x-bot/data/promoter_memory.sqlite}"

cd "$ROOT"
exec "$PY" -m cli.main run "$BOT_DIR/modules/apollo/thread_engagement.ainl" --strict --label _thread_continue \
  --http-timeout-s "$HTTP_TIMEOUT_S" \
  --enable-adapter bridge \
  --enable-adapter memory \
  --memory-db "$AINL_MEMORY_DB" \
  --bridge-endpoint "kv.get=${GATEWAY}/v1/kv.get" \
  --bridge-endpoint "kv.set=${GATEWAY}/v1/kv.set" \
  --bridge-endpoint "x.search=${GATEWAY}/v1/x.search" \
  --bridge-endpoint "x.search_users=${GATEWAY}/v1/x.search_users" \
  --bridge-endpoint "x.follow=${GATEWAY}/v1/x.follow" \
  --bridge-endpoint "x.like=${GATEWAY}/v1/x.like" \
  --bridge-endpoint "x.get_conversation=${GATEWAY}/v1/x.get_conversation" \
  --bridge-endpoint "promoter.thread_continue=${GATEWAY}/v1/promoter.thread_continue" \
  --bridge-endpoint "promoter.awareness_boost=${GATEWAY}/v1/promoter.awareness_boost" \
  --bridge-endpoint "llm.classify=${GATEWAY}/v1/llm.classify" \
  --bridge-endpoint "promoter.heuristic_scores=${GATEWAY}/v1/promoter.heuristic_scores" \
  --bridge-endpoint "promoter.process_tweet=${GATEWAY}/v1/promoter.process_tweet"
