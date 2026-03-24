#!/usr/bin/env bash
# Step 1 safety net: strict-check Apollo promoter graph + shared modules + gateway tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Prefer repo .venv (matches Makefile / CI) so pytest is available.
if [ -z "${PYTHON+x}" ] && [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi
PYTEST="${PYTEST:-$PYTHON -m pytest}"

echo "==> strict: apollo-x-bot/ainl-x-promoter.ainl"
"$PYTHON" -m cli.main check --strict apollo-x-bot/ainl-x-promoter.ainl
echo "==> strict: modules/common/promoter_discover_from_tweets.ainl"
"$PYTHON" -m cli.main check --strict modules/common/promoter_discover_from_tweets.ainl
echo "==> strict: modules/llm/promoter_daily_post_payload.ainl"
"$PYTHON" -m cli.main check --strict modules/llm/promoter_daily_post_payload.ainl
echo "==> pytest: apollo gateway + strict common modules"
$PYTEST -q tests/test_apollo_x_gateway.py tests/test_common_llm_modules_strict.py
echo "==> check_apollo_promoter: ok"
