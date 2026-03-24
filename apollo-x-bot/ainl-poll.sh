#!/usr/bin/env bash
# AINL X Promoter — poll runner (no --strict; upstream graph has pre-existing strict errors)
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

PY="${PYTHON:-/data/.openclaw/workspace/ainativelang/.venv-ainl/bin/python3}"
GATEWAY="${PROMOTER_GATEWAY_URL:-http://127.0.0.1:17301}"
GATEWAY="${GATEWAY%/}"

export PROMOTER_STATE_PATH="${PROMOTER_STATE_PATH:-$BOT_DIR/data/promoter_state.sqlite}"
export AINL_MEMORY_DB="${AINL_MEMORY_DB:-$BOT_DIR/data/promoter_memory.sqlite}"

cd "$ROOT"
exec "$PY" -m cli.main run "$BOT_DIR/ainl-x-promoter.ainl" --label _poll \
  --http-timeout-s 60 \
  --unknown-op-policy skip \
  --enable-adapter bridge \
  --enable-adapter memory \
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
