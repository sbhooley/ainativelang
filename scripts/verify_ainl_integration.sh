#!/usr/bin/env bash
# Post-install verification for AINL + OpenClaw integration
# Run after setup to confirm everything is working.

set -e

echo "=== AINL + OpenClaw Integration Verification ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
  local desc="$1"
  local cmd="$2"
  echo -n "Checking: $desc... "
  if eval "$cmd" >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}✗${NC}"
    ((FAIL++))
    return 1
  fi
}

check_file() {
  local desc="$1"
  local path="$2"
  echo -n "Checking: $desc... "
  if [ -f "$path" ]; then
    echo -e "${GREEN}✓${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}✗${NC}"
    ((FAIL++))
    return 1
  fi
}

check_dir() {
  local desc="$1"
  local path="$2"
  echo -n "Checking: $desc... "
  if [ -d "$path" ]; then
    echo -e "${GREEN}✓${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}✗${NC}"
    ((FAIL++))
    return 1
  fi
}

# 1. File structure
echo "--- File Structure ---"
check_file "Project lock file" "/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/aiNativeLang.yml"
check_dir "AINL virtual environment" "/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl"
check_dir "AINL bridge modules" "/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/openclaw/bridge"
check_dir "AINL intelligence scripts" "/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/intelligence"

# 2. Python package installation
echo ""
echo "--- Python Installation ---"
if /Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/python3 -c "from openclaw.bridge.cron_drift_check import run_report" 2>/dev/null; then
  echo -e "Import openclaw.bridge: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "Import openclaw.bridge: ${RED}✗${NC}"
  ((FAIL++))
fi

if /Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/python3 -c "from cli.main import main" 2>/dev/null; then
  echo -e "Import ainl CLI: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "Import ainl CLI: ${RED}✗${NC}"
  ((FAIL++))
fi

# 3. Binary availability
echo ""
echo "--- Binary Availability ---"
if [ -x /Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/ainl ]; then
  echo -e "ainl binary: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "ainl binary: ${RED}✗${NC}"
  ((FAIL++))
fi

if /Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/ainl-mcp --version >/dev/null 2>&1; then
  echo -e "ainl-mcp binary: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "ainl-mcp binary: ${RED}✗${NC}"
  ((FAIL++))
fi

# 4. OpenClaw configuration
echo ""
echo "--- OpenClaw Configuration ---"
if grep -q '"ainl"' /Users/clawdbot/.openclaw/openclaw.json; then
  echo -e "MCP server registered in openclaw.json: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "MCP server registered in openclaw.json: ${RED}✗${NC}"
  ((FAIL++))
fi

if grep -q '"/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin"' /Users/clawdbot/.openclaw/openclaw.json; then
  echo -e "AINL venv in exec.pathPrepend: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "AINL venv in exec.pathPrepend: ${RED}✗${NC}"
  ((FAIL++))
fi

if grep -q 'AINL_MEMORY_DB' /Users/clawdbot/.openclaw/openclaw.json; then
  echo -e "AINL env vars in shellEnv: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "AINL env vars in shellEnv: ${RED}✗${NC}"
  ((FAIL++))
fi

# 5. Cron jobs
echo ""
echo "--- Cron Jobs ---"
AINL_CRON_COUNT=$(openclaw cron list 2>/dev/null | grep -i ainl | wc -l | tr -d ' ')
if [ "$AINL_CRON_COUNT" -ge 3 ]; then
  echo -e "AINL cron jobs registered: ${GREEN}✓${NC} ($AINL_CRON_COUNT jobs)"
  ((PASS++))
else
  echo -e "AINL cron jobs registered: ${RED}✗${NC} (found $AINL_CRON_COUNT, expected ≥3)"
  ((FAIL++))
fi

# 6. Directories
echo ""
echo "--- Runtime Directories ---"
check_dir "AINL memory DB parent" "/Users/clawdbot/.openclaw/workspace/.ainl"
check_dir "IR cache" "/Users/clawdbot/.openclaw/workspace/.cache/ainl/ir"
check_dir "Daily memory dir" "/Users/clawdbot/.openclaw/workspace/memory"

# 7. Service status (infrastructure)
echo ""
echo "--- Infrastructure (Optional) ---"
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787 2>/dev/null | grep -q 200; then
  echo -e "Caddy (port 8787): ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "Caddy (port 8787): ${YELLOW}?${NC} (not running or not configured)"
fi

if ps aux | grep -v grep | grep -q '[m]addy'; then
  echo -e "Maddy mail server: ${GREEN}✓${NC}"
  ((PASS++))
else
  echo -e "Maddy mail server: ${YELLOW}?${NC} (not running)"
fi

# Summary
echo ""
echo "==================================="
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}All critical checks passed!${NC}"
  echo "AINL integration is ready to use."
  echo ""
  echo "Next steps:"
  echo "  ainl status              # Health check"
  echo "  openclaw cron list       # View scheduled jobs"
  echo "  tail -f ~/.openclaw/logs/gateway.log  # Monitor logs"
  exit 0
else
  echo -e "${RED}Some checks failed. Review the output above.${NC}"
  echo ""
  echo "Common fixes:"
  echo "  - Re-run: ./scripts/setup_ainl_integration.sh --workspace /Users/clawdbot/.openclaw/workspace"
  echo "  - Ensure venv installed: cd AI_Native_Lang && pip install -e \".[mcp]\""
  echo "  - Restart gateway: openclaw gateway restart"
  exit 1
fi
