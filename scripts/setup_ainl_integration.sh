#!/usr/bin/env bash
# One-command setup for AINL v1.2.8 OpenClaw integration.
# Prerequisites: OpenClaw >= 2026.3.22 (includes native OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT support)
# This script:
#  - Sets required environment/config in OpenClaw (via gateway config.patch)
#  - Reduces reserveTokens for more aggressive compaction
#  - Enables embeddings and sets tight token budget for token-aware startup
#  - Enforces graph-preferred execution mode
#  - Copies/registers bridge wrappers (token-aware startup, token budget alerts, weekly trends, etc.)
#  - Optionally adds cron jobs (pass --with-cron)
#  - Restarts the gateway
#
# Usage:
#   ./setup_ainl_integration.sh [--with-cron]
#
# Requires: openclaw CLI on PATH, gateway running.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_DIR="$ROOT/openclaw/bridge"
WRAPPERS_DIR="$BRIDGE_DIR/wrappers"
RUNNER="$BRIDGE_DIR/run_wrapper_ainl.py"

ADD_CRON=0
if [[ "${1:-}" == "--with-cron" ]]; then
  ADD_CRON=1
fi

echo "== AINL v1.2.8 OpenClaw Integration Setup =="

# 1. Config patch via gateway (includes OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1)
echo "-> Applying OpenClaw configuration (env vars + compaction)..."
openclaw gateway config.patch "$ROOT/scripts/config_patch_ainl_integration.json" || {
  echo "Applying config via direct gateway config.patch..."
  openclaw gateway config.patch '{"env":{"vars":{"AINL_STARTUP_CONTEXT_TOKEN_MIN":"100","AINL_STARTUP_CONTEXT_TOKEN_MAX":"100","AINL_STARTUP_USE_EMBEDDINGS":"1","AINL_EMBEDDING_MODE":"lite","AINL_EXECUTION_MODE":"graph-preferred","OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT":"1"}},"agents":{"defaults":{"compaction":{"reserveTokens":30000}}}}'
}

# 2. Ensure wrappers directory exists
mkdir -p "$WRAPPERS_DIR"

# 3. Copy wrapper files (if not already present)
echo "-> Registering bridge wrappers..."
# Copy token_aware_startup_context.ainl if missing
if [ ! -f "$WRAPPERS_DIR/token_aware_startup_context.ainl" ]; then
  cp "$ROOT/intelligence/token_aware_startup_context.lang" "$WRAPPERS_DIR/token_aware_startup_context.ainl"
  echo "  + token_aware_startup_context.ainl"
fi
# Other wrappers are part of the repo; just ensure they exist
for w in token_budget_alert weekly_token_trends ttl_memory_tuner embedding_memory_pilot; do
  if [ -f "$BRIDGE_DIR/wrappers/$w.ainl" ]; then
    echo "  + $w.ainl (present)"
  fi
done

# 4. Update run_wrapper_ainl.py registry (idempotent)
echo "-> Updating wrapper registry in run_wrapper_ainl.py..."
python3 - <<'PY'
import re, sys
path = sys.argv[1]
with open(path, 'r') as f:
  content = f.read()
# Ensure token-aware-startup entry
if '"token-aware-startup":' not in content:
  content = content.replace(
    'WRAPPERS = {',
    'WRAPPERS = {\n    "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",'
  )
# Comment out email-monitor if present
if '"email-monitor":' in content:
  content = re.sub(r'"email-monitor":.*,#?.*', '# "email-monitor": _BRIDGE_DIR / "wrappers" / "email_monitor.ainl",  # disabled: requires openclaw mail plugin', content)
with open(path, 'w') as f:
  f.write(content)
print("Registry updated")
PY "$RUNNER"

# 5. No host patch needed for OpenClaw >= 2026.3.22 (native support)

# 6. Add cron jobs if requested
if [[ $ADD_CRON -eq 1 ]]; then
  echo "-> Adding cron jobs..."
  # Token-aware startup context
  openclaw cron add \
    --name "Token-Aware Startup Context" \
    --cron "*/15 * * * *" \
    --session-key "agent:default:ainl-advocate" \
    --message "Run: cd $ROOT && python3 $RUNNER token-aware-startup" \
    --description "AINL token-aware startup context generator" \
    || echo "Cron add may have failed (job might exist already)."

  # Token budget alert (daily 23:00 UTC)
  openclaw cron add \
    --name "AINL Token Budget Alert" \
    --cron "0 23 * * *" \
    --session-key "agent:default:ainl-advocate" \
    --message "Run: cd $ROOT && python3 $RUNNER token-budget-alert" \
    --description "Daily token usage report" \
    || true

  # Weekly token trends (Sunday 09:00 UTC)
  openclaw cron add \
    --name "AINL Weekly Token Trends" \
    --cron "0 9 * * 0" \
    --session-key "agent:default:ainl-advocate" \
    --message "Run: cd $ROOT && python3 $RUNNER weekly-token-trends" \
    --description "Weekly token usage trends" \
    || true
fi

# 7. Restart gateway
echo "-> Restarting OpenClaw gateway..."
openclaw gateway restart

echo "== Setup Complete =="
echo "Next steps:"
echo "- Verify: openclaw doctor --non-interactive"
echo "- Check token-aware startup job: openclaw cron list | grep -i token"
echo "- Inspect generated context: cat .openclaw/bootstrap/session_context.md"
echo "- Monitor token usage in session status (/status) over next few hours."
echo ""
echo "Note: Requires OpenClaw >= 2026.3.22 for native OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT support."
