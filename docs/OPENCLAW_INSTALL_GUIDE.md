# OpenClaw + AINL Installation Guide

This guide ensures a complete AINL integration for OpenClaw in **3 minutes or less**.

## Prerequisites

- OpenClaw installed and running
- Python 3.10+ available (`python3 --version`)
- Git installed
- Homebrew (macOS) or appropriate package manager

## One-Command Setup

From your OpenClaw workspace root:

```bash
# Clone AINL into the workspace
git clone https://github.com/sbhooley/ainativelang.git AI_Native_Lang
cd AI_Native_Lang

# Install Python dependencies into isolated venv
python3 -m venv .venv-ainl
source .venv-ainl/bin/activate
pip install -e ".[mcp]" --quiet

# Run the OpenClaw integration installer
./scripts/setup_ainl_integration.sh --workspace /Users/clawdbot/.openclaw/workspace
```

That's it! The script handles:
- ✅ MCP server registration (`ainl-mcp`)
- ✅ Environment variable injection (`env.shellEnv`)
- ✅ SQLite schema bootstrap (memory tables)
- ✅ Gold-standard cron job registration
- ✅ PATH configuration for `ainl` and `ainl-mcp`
- ✅ Gateway restart to load changes

## What the Installer Does

### 1. Writes `aiNativeLang.yml` (if missing)
Project lock file at `AI_Native_Lang/aiNativeLang.yml` that documents the integration and allows easy recreation.

### 2. Merges Environment Configuration
Adds these keys to `openclaw.json.env.shellEnv`:
- `AINL_MEMORY_DB` — SQLite memory database path
- `AINL_EMBEDDING_MEMORY_DB` — Vector memory path
- `MONITOR_CACHE_JSON` — Token monitor state
- `AINL_IR_CACHE_DIR` — Compiled graph cache
- `OPENCLAW_MEMORY_DIR` / `OPENCLAW_DAILY_MEMORY_DIR` — Daily markdown logs
- `AINL_EXECUTION_MODE=graph-preferred` — Use graph runtime when available
- `AINL_WEEKLY_TOKEN_BUDGET_CAP=100000` — Weekly token guard
- And OpenClaw integration flags

### 3. Adds `ainl` to PATH
Updates `openclaw.json.tools.exec.pathPrepend` to include the AINL virtual environment, ensuring `ainl` and `ainl-mcp` are found by OpenClaw subprocesses.

### 4. Registers Gold-Standard Cron Jobs
Three core cron jobs (if not already present):
- **AINL Context Injection** — every 5 minutes
- **AINL Session Summarizer** — daily at 3 AM
- **AINL Weekly Token Trends** — Sundays at 9 AM

Plus optional jobs (if present in `aiNativeLang.yml`):
- AINL Thread Engagement
- Infrastructure Watchdog
- etc.

### 5. Bootstraps SQLite Tables
Creates `weekly_remaining_v1` table for rolling token budget tracking.

### 6. Restarts Gateway
Applies config changes and loads the MCP server.

## Verification

After setup:

```bash
# Check AINL MCP server is registered
grep -A2 '"ainl":' ~/.openclaw/openclaw.json

# Verify cron jobs
openclaw cron list | grep -i ainl

# Test AINL CLI
cd /Users/clawdbot/.openclaw/workspace/AI_Native_Lang
./.venv-ainl/bin/ainl status

# Check memory DB
ls -la ~/.openclaw/workspace/.ainl/
```

Expected:
- `ainl` MCP server present in `openclaw.json`
- 3+ AINL cron jobs listed
- `ainl status` shows "All checks green"
- `.ainl/` directory exists with SQLite files

## Troubleshooting

### "ainl: command not found"
The installer adds the venv to `exec.pathPrepend`. If running `ainl` manually, activate the venv:
```bash
source /Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/activate
```
Or use the full path: `/Users/clawdbot/.openclaw/workspace/AI_Native_Lang/.venv-ainl/bin/ainl`

### "ModuleNotFoundError: openclaw"
The `openclaw` Python module is part of the AINL repo (directory `openclaw/`). Ensure it's included in the editable install:
```bash
cd AI_Native_Lang
pip install -e ".[mcp]"
```
The `pyproject.toml` includes `openclaw` in `packages.find.include`.

### Cron jobs failing with "Delivering to Telegram requires target <chatId>"
The Infrastructure Watchdog job needs a Telegram target configured. The installer sets this automatically based on your `openclaw.json.channels.telegram.allowFrom`. If missing, manually edit the cron or re-run the installer.

### MCP server not appearing in `openclaw.json`
The `ainl install openclaw` command writes the MCP config. Ensure the installer completed successfully and the gateway was restarted. You can manually add:
```json
"mcp": {
  "servers": {
    "ainl": {
      "command": "ainl-mcp",
      "args": []
    }
  }
}
```
Then restart the gateway: `openclaw gateway restart`

## Advanced

- **Dry run**: `./scripts/setup_ainl_integration.sh --dry-run`
- **Custom workspace**: `--workspace /path/to/workspace`
- **Manual installation**: `ainl install openclaw --workspace /path/to/workspace`
- **Re-run setup**: Safe to re-run; it's idempotent.
- **Cron drift check**: `cd AI_Native_Lang && python3 openclaw/bridge/cron_drift_check.py`

## Files Created/Modified

| Path | Purpose |
|------|---------|
| `AI_Native_Lang/aiNativeLang.yml` | Project lock file |
| `AI_Native_Lang/.venv-ainl/` | Virtual environment (created by you) |
| `~/.openclaw/openclaw.json` | Updated with env vars, PATH, and MCP |
| `~/.openclaw/workspace/.ainl/` | SQLite memory databases |
| `~/.cache/ainl/ir` | Compiled graph cache |

## Support

- AINL Docs: https://www.ainativelang.com/docs
- OpenClaw AINL Gold Standard: https://www.ainativelang.com/docs/operations/OPENCLAW_AINL_GOLD_STANDARD
- Repo: https://github.com/sbhooley/ainativelang

---

**Installation time**: ~3 minutes (clone + pip install + setup script)
