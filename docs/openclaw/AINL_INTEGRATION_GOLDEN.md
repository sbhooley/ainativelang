# Golden Instructions: AINL Integration for OpenClaw

**Goal:** Achieve 85–95% token savings on session bootstrap by using AINL's curated `session_context.md` instead of full `MEMORY.md`.

---

## 1. Prerequisites

- OpenClaw installed and running
- AINL repository cloned and available at `$WORKSPACE/AI_Native_Lang`
- `ainl` CLI in PATH (from AINL install)

---

## 2. Pin Workspace & Environment

Set consistent paths so all cron jobs and agents use the same locations.

**Add to OpenClaw config (`openclaw.json` under `env.vars`):**

```bash
openclaw gateway config.patch '{
  "env": {
    "vars": {
      "OPENCLAW_WORKSPACE": "/full/path/to/workspace",
      "OPENCLAW_MEMORY_DIR": "/full/path/to/workspace/memory",
      "OPENCLAW_DAILY_MEMORY_DIR": "/full/path/to/workspace/memory",
      "AINL_FS_ROOT": "/full/path/to/workspace",
      "AINL_MEMORY_DB": "/full/path/to/workspace/.ainl/ainl_memory.sqlite3",
      "MONITOR_CACHE_JSON": "/full/path/to/workspace/.ainl/monitor_state.json",
      "AINL_EMBEDDING_MEMORY_DB": "/full/path/to/workspace/.ainl/embedding_memory.sqlite3",
      "AINL_IR_CACHE_DIR": "/full/path/to/workspace/.cache/ainl/ir",
      "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": "true"
    }
  }
}'
```

Replace `/full/path/to/workspace` with your actual workspace path (e.g., `/Users/clawdbot/.openclaw/workspace`).

The gateway will restart automatically.

---

## 3. Shell Profile (optional but recommended)

Add to `~/.zprofile` (or shell equivalent) so interactive shells have the same environment:

```bash
# AINL workspace pin
export OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace"
. "$OPENCLAW_WORKSPACE/AI_Native_Lang/tooling/openclaw_workspace_env.example.sh"
eval "$(ainl profile emit-shell openclaw-default)"
```

Then `source ~/.zprofile` or open a new terminal.

---

## 4. Cron Jobs (schedule)

Ensure these AINL intelligence jobs exist and are enabled. Use `openclaw cron` to manage.

### a) Context injection (runs frequently to keep session_context.md fresh)

**Implementation:** `token-aware-startup` wrapper (see `docs/openclaw/TOKEN_AWARE_STARTUP_CONTEXT.md`)

```bash
openclaw cron add '{
  "name": "AINL Context Injection",
  "schedule": { "kind": "every", "everyMs": 300000 },
  "payload": {
    "kind": "agentTurn",
    "agentId": "ainl-advocate",
    "message": "run intelligence: context"
  },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}'
```

### b) Session summarizer (daily)

```bash
openclaw cron add '{
  "name": "AINL Session Summarizer",
  "schedule": { "kind": "cron", "expr": "0 3 * * *" },
  "payload": {
    "kind": "agentTurn",
    "agentId": "ainl-advocate",
    "message": "run intelligence: summarizer"
  },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}'
```

### c) Weekly token trends bridge (publishes weekly_remaining_v1)

```bash
openclaw cron add '{
  "name": "AINL Weekly Token Trends",
  "schedule": { "kind": "cron", "expr": "0 9 * * 0" },
  "payload": {
    "kind": "agentTurn",
    "agentId": "ainl-advocate",
    "message": "run bridge: weekly-token-trends"
  },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}'
```

Adjust schedules as needed; these are proven defaults.

---

## 5. Bootstrap Preference (upgrade-safe)

We control the bootstrap order via environment variable instead of patching code.

- Already set above: `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true` in OpenClaw `env.vars`.
- **Important:** The OpenClaw host binary must contain the small loader change that respects this env var. If you control the host installation, patch `.../dist/workspace-*.js` to check that env var before resolving the memory bootstrap file.

**Patch snippet to apply once on the host (survives until OpenClaw upgrade):**

```javascript
// In resolveMemoryBootstrapEntry(resolvedDir) function:
const preferSessionContext = typeof process !== 'undefined' && process.env && (process.env.OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT === 'true' || process.env.OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT === '1');
if (preferSessionContext) {
  const sessionContextPath = path.join(resolvedDir, ".openclaw", "bootstrap", "session_context.md");
  try {
    await fs$1.access(sessionContextPath);
    return { name: "session_context.md", filePath: sessionContextPath };
  } catch {}
}
// then fall back to MEMORY.md files...
```

After patching, restart OpenClaw (`openclaw gateway restart`).

---

## 6. Verification

1. **Check env:** `openclaw doctor --non-interactive` should show `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true` and all pinned paths.

2. **Wait for first context run** (or trigger it by sending `"run intelligence: context"` to the `ainl-advocate` agent). Then confirm:
   ```bash
   ls -la $OPENCLAW_WORKSPACE/.openclaw/bootstrap/session_context.md
   ```
   File should exist and be recent.

3. **Start a new agent session** and inspect the system prompt (or ask the agent what bootstrap files it loaded). It should reference `session_context.md` when available, not full `MEMORY.md`.

4. **Bridge sizing:** Run once to set initial bridge char limit:
   ```bash
   cd $OPENCLAW_WORKSPACE/AI_Native_Lang
   python3 scripts/bridge_sizing_probe.py --json
   ```
   Output suggests `AINL_BRIDGE_REPORT_MAX_CHARS`. Add that to OpenClaw `env.vars` if you want tighter defaults.

---

## 7. Optional: Cost-Tight Profile

After measuring defaults for a few days, switch to the `cost-tight` AINL profile for even more aggressive caps:

```bash
# In ~/.zprofile, change:
# eval "$(ainl profile emit-shell openclaw-default)"
eval "$(ainl profile emit-shell cost-tight)"
```

Then gate restart. Monitor token usage in `MONITOR_CACHE_JSON` and adjust `AINL_WEEKLY_TOKEN_BUDGET_CAP` accordingly.

---

## 8. All-In-One Setup Script (optional)

Create `scripts/setup_ainl_integration.sh` in your workspace:

```bash
#!/usr/bin/env bash
set -euo pipefail

WS="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
cat <<'JSON' | openclaw gateway config.patch - "$(date -u +"%Y-%m-%d %H:%M UTC") - Setup AINL integration"
{
  "env": {
    "vars": {
      "OPENCLAW_WORKSPACE": "'''"$WS"'''",
      "OPENCLAW_MEMORY_DIR": "'''"$WS/memory"'''",
      "OPENCLAW_DAILY_MEMORY_DIR": "'''"$WS/memory"'''",
      "AINL_FS_ROOT": "'''"$WS"'''",
      "AINL_MEMORY_DB": "'''"$WS/.ainl/ainl_memory.sqlite3"'''",
      "MONITOR_CACHE_JSON": "'''"$WS/.ainl/monitor_state.json"'''",
      "AINL_EMBEDDING_MEMORY_DB": "'''"$WS/.ainl/embedding_memory.sqlite3"'''",
      "AINL_IR_CACHE_DIR": "'''"$WS/.cache/ainl/ir"'''",
      "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": "true"
    }
  }
}
JSON

# Add cron jobs (idempotent)
openclaw cron add '{
  "name": "AINL Context Injection",
  "schedule": { "kind": "every", "everyMs": 300000 },
  "payload": { "kind": "agentTurn", "agentId": "ainl-advocate", "message": "run intelligence: context" },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}' || true

openclaw cron add '{
  "name": "AINL Session Summarizer",
  "schedule": { "kind": "cron", "expr": "0 3 * * *" },
  "payload": { "kind": "agentTurn", "agentId": "ainl-advocate", "message": "run intelligence: summarizer" },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}' || true

openclaw cron add '{
  "name": "AINL Weekly Token Trends",
  "schedule": { "kind": "cron", "expr": "0 9 * * 0" },
  "payload": { "kind": "agentTurn", "agentId": "ainl-advocate", "message": "run bridge: weekly-token-trends" },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}' || true

# Optional but recommended: Auto-Tuner (requires modifying run_intelligence.py and adding the script)
# Step 1: Add the auto_tune_ainl_caps entry to PROGRAMS in scripts/run_intelligence.py:
#   'auto_tune_ainl_caps': 'scripts/auto_tune_ainl_caps.py',
# Step 2: Create scripts/auto_tune_ainl_caps.py (see docs/AINL_AUTO_TUNER.md)
# Step 3: Add cron job:
openclaw cron add '{
  "name": "AINL Auto-Tune Caps",
  "schedule": { "kind": "cron", "expr": "0 11 * * 0" },
  "payload": { "kind": "agentTurn", "agentId": "ainl-advocate", "message": "run intelligence: auto_tune_ainl_caps" },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}' || true

echo "AINL integration configured. Restart OpenClaw if needed."
```

Run it once after installing AINL.

---

**That’s it.** Other agents can follow these steps to reproduce the exact setup.

## Appendix: Auto-Tuner Details

See `docs/AINL_AUTO_TUNER.md` for full documentation on the auto-tuner program, configuration, safety, and troubleshooting.
