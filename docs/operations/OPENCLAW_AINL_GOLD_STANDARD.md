# OpenClaw + AINL — gold standard (install / upgrade)
> **Start here if you are new:** [`docs/QUICKSTART_OPENCLAW.md`](../QUICKSTART_OPENCLAW.md) — `ainl install openclaw`, `ainl status`, and `ainl doctor --ainl` before you tune caps or cron.  <!-- AINL-OPENCLAW-TOP5 -->

> **Fastest onboarding:** use **`ainl install openclaw`** — see [`AI_AGENT_QUICKSTART_OPENCLAW.md`](../../AI_AGENT_QUICKSTART_OPENCLAW.md) or §1 *Quickstart (5 minutes)* below. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

**Purpose:** Canonical reference for **agents and operators** after **`pip install`** / **`ainl install-mcp --host openclaw`** (or similar). Follow this to align **profiles**, **caps**, **cron**, **shared paths**, and **verification** so token savings and **`budget_hydrate`** behavior show up in real sessions. **Adapt numbers** to your measured workload (`bridge-sizing-probe`); the structure stays the same.

**AINL v1.3.3 host briefing (what the repo ships vs what OpenClaw must do; current PyPI):** [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md) — copy-paste ready for operators; **`tooling/bot_bootstrap.json`** → **`openclaw_host_ainl_1_2_8`**.

**See also:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) (bundle index) · [`AINL_PROFILES.md`](AINL_PROFILES.md) · [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) · [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`../INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md) · [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) · [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)

---

## 0. Prerequisites

- OpenClaw installed and running
- AINL repository cloned and available at `$WORKSPACE/AI_Native_Lang`
- `ainl` CLI in PATH (from AINL install)

## 1. Progressive Disclosure (Recommended Learning Path)

The AINL + OpenClaw integration has many moving parts. To avoid overwhelm, follow the tier that matches your needs.

### Quickstart (5 minutes)

Goal: Get AINL working with safe defaults.

1. Run the all‑in‑one setup script (provided in this repo):
   ```bash
   cd $WORKSPACE/AI_Native_Lang
   ./scripts/setup_ainl_integration.sh
   ```
2. Restart OpenClaw: `openclaw gateway restart`
3. Run health check: `ainl status`
   - Should show “All checks green” or list any missing items
4. Wait for the next context injection (every 5 minutes) and confirm `session_context.md` appears.
5. Done. Let the system run; revisit tuning only if you hit caps.

### Standard (15 minutes)

Goal: Understand and tune caps, verify cron jobs, interpret trends.

1. Complete Quickstart.
2. Read §2 (Critical caps) and adjust `AINL_BRIDGE_REPORT_MAX_CHARS` based on your `session_context.md` size.
3. Check weekly trends: `sqlite3 ~/.openclaw/workspace/.ainl/ainl_memory.sqlite3 "SELECT * FROM weekly_remaining_v1 ORDER BY week_start DESC LIMIT 4;"` (legacy table; optional — confirms schema or older direct rows). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->) The rolling budget is published primarily to **`memory_records`** (`namespace='workflow'`, `record_kind='budget.aggregate'`, `record_id='weekly_remaining_v1'`); you can inspect the latest payload with a `SELECT payload_json … FROM memory_records …` query on that key if needed. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> **`ainl status`** reflects this automatically: it prefers the legacy table when a non-null row exists, otherwise falls back to **`weekly_remaining_tokens`** from the memory aggregate. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
4. Adjust `AINL_WEEKLY_TOKEN_BUDGET_CAP` if you’re consistently >80% used.
5. Verify all cron jobs present: `openclaw cron list`
6. Review Token Cost Tracker Telegram messages; ensure they’re arriving.
7. Optional: run `ainl bridge-sizing-probe --json` to get empirical report sizes.

### Advanced (60 minutes)

Goal: Customize workflows, enable embeddings, tune performance.

1. Complete Standard.
2. Explore `intelligence/` programs; read `AGENT_AINL_OPERATING_MODEL.md`.
3. Enable embedding retrieval pilot (see `EMBEDDING_RETRIEVAL_PILOT.md`).
4. Experiment with custom adapters or WASM steps.
5. Set up cap auto‑tuner: `python3 scripts/run_intelligence.py auto_tune_ainl_caps` (dry‑run first).
6. Review `TOKEN_AND_USAGE_OBSERVABILITY.md` for alerting and dashboards.
7. Consider moving from `env.shellEnv` to profile emission if you run many ad‑hoc `ainl` commands.

---

## 1. (renumbered) Critical caps (start here, then tighten)

Set **after** you understand your gateway; **adjust** after `ainl bridge-sizing-probe` (see §5).

| Variable | Example start | Notes |
|----------|----------------|--------|
| `AINL_BRIDGE_REPORT_MAX_CHARS` | `500` | Bridge report size; raise only if evidence shows truncation pain. |
| `AINL_WEEKLY_TOKEN_BUDGET_CAP` | `200000` | Match **your** real weekly budget. |
| `PROMOTER_LLM_MAX_PROMPT_CHARS` | `2000` | **Gateway (Apollo)** — not in `ainl_profiles.json`; set on the promoter process. |
| `PROMOTER_LLM_MAX_COMPLETION_TOKENS` | `500` | **Gateway** — same. |

Staging order and hydrate flags: [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md).

### Startup bootstrap caps (AINL token-aware context)

These clamp the *allocation* used by `intelligence/token_aware_startup_context.lang` when it builds `session_context.md`:

- `AINL_STARTUP_CONTEXT_TOKEN_MIN` / `AINL_STARTUP_CONTEXT_TOKEN_MAX`
- `AINL_STARTUP_USE_EMBEDDINGS` (embedding top-k candidate path; safe fallback enabled)

Important activation rules:

- Embedding top-k only triggers when `AINL_EMBEDDING_MODE` is **not** `stub` (so profiles can leave `AINL_STARTUP_USE_EMBEDDINGS=1` while still being safe by default).
- When embeddings are real, run the embedding pilot at least once so `workflow.session_summary` text is indexed (see [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md)).

To tune startup tokens, start from your profile values, then adjust based on measured `session_context.md` length and user-visible behavior.

## 1. Environment profile

- **Baseline (first install):** `openclaw-default` — safe defaults before you have measurements.
- **After measuring** (bridge report size, weekly trends, intelligence runs): switch to **`cost-tight`** for stricter bridge report caps and the same conservative defaults.

```bash
# Baseline
eval "$(ainl profile emit-shell openclaw-default)"

# After measured tuning (typical “cost-tight” path)
eval "$(ainl profile emit-shell cost-tight)"
```

Pin **one workspace** so SQLite, cache JSON, and FS roots stay consistent (see [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md)):

```bash
export OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
. tooling/openclaw_workspace_env.example.sh
eval "$(ainl profile emit-shell openclaw-default)"   # or cost-tight
```

### Host workspace & environment pin (OpenClaw `env.vars`)

To make sure cron jobs, bridges, and agents all use the same paths (and to support upgrade-safe bootstrap preference), add these under **OpenClaw `env.vars`**:

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

Replace `/full/path/to/workspace` with your actual workspace path. Restart is handled by the gateway.

---

## 2. Critical caps (start here, then tighten)

Set **after** you understand your gateway; **adjust** after `ainl bridge-sizing-probe` (see §5).

| Variable | Example start | Notes |
|----------|----------------|--------|
| `AINL_BRIDGE_REPORT_MAX_CHARS` | `500` | Bridge report size; raise only if evidence shows truncation pain. |
| `AINL_WEEKLY_TOKEN_BUDGET_CAP` | `200000` | Match **your** real weekly budget. |
| `PROMOTER_LLM_MAX_PROMPT_CHARS` | `2000` | **Gateway (Apollo)** — not in `ainl_profiles.json`; set on the promoter process. |
| `PROMOTER_LLM_MAX_COMPLETION_TOKENS` | `500` | **Gateway** — same. |

Staging order and hydrate flags: [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md).

### Startup bootstrap caps (AINL token-aware context)

These clamp the *allocation* used by `intelligence/token_aware_startup_context.lang` when it builds `session_context.md`:

- `AINL_STARTUP_CONTEXT_TOKEN_MIN` / `AINL_STARTUP_CONTEXT_TOKEN_MAX`
- `AINL_STARTUP_USE_EMBEDDINGS` (embedding top-k candidate path; safe fallback enabled)

Important activation rules:

- Embedding top-k only triggers when `AINL_EMBEDDING_MODE` is **not** `stub` (so profiles can leave `AINL_STARTUP_USE_EMBEDDINGS=1` while still being safe by default).
- When embeddings are real, run the embedding pilot at least once so `workflow.session_summary` text is indexed (see [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md)).

To tune startup tokens, start from your profile values, then adjust based on measured `session_context.md` length and user-visible behavior.

---

## 3. Cron schedule (recommended defaults)

Proven OpenClaw defaults (use `openclaw cron`), with the agent sending the right host actions into AINL:

### a) AINL Context Injection (every 5 minutes; keeps bootstrap fresh)

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

### b) AINL Session Summarizer (daily)

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

### c) AINL Weekly Token Trends Bridge (Sunday; publishes `weekly_remaining_v1`)

The weekly bridge publishes the rolling budget **primarily** to **`memory_records`** (`namespace='workflow'`, `record_kind='budget.aggregate'`, `record_id='weekly_remaining_v1'`). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> **`ainl install openclaw`** still bootstraps the legacy **`weekly_remaining_v1`** SQLite table for compatibility; **`ainl status`** reads that table when present and non-null, otherwise shows **`weekly_remaining_tokens`** from the latest memory aggregate. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

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

Notes:
- Replace `agentId: "ainl-advocate"` and messages if your host uses different agent IDs or wrapper routes.
- The wrapper path(s) behind `weekly-token-trends` live under [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md).
- All AINL jobs must share the same workspace paths via `OPENCLAW_WORKSPACE` (and derived env vars), see [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md).

---

## 4. Host behavior (required for savings to show in chat)

Without this, AINL jobs may run “correctly” but **users do not see** reduced tokens at session start.

### Host contract (non-negotiable)

1. **Bootstrap load order:** On every new session, prefer **`.openclaw/bootstrap/session_context.md`** if present; fall back to **`MEMORY.md`** only when the curated bootstrap file does not exist.
2. **Upgrade safety:** honor `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true` so this preference survives host upgrades without fragile hard-coded behavior.
3. **Session continuity:** the above order must apply consistently for subsequent sessions/continuity turns, not only the first run.

### If your OpenClaw host does not yet respect the env var (fallback)

Only in that case, apply a one-time loader shim (expected to be re-applied after OpenClaw upgrades):

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

### Shared paths (required)

All cron, bridge, and intelligence processes must use the **same** resolved paths:

- `OPENCLAW_WORKSPACE`
- `OPENCLAW_MEMORY_DIR`, `AINL_FS_ROOT`
- `AINL_MEMORY_DB`, `MONITOR_CACHE_JSON`

Details: [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md).

---

## 5. Verification cadence

1. **Env check:** verify `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true` and pinned paths are present.
2. **Wait for first context run** and confirm:
   ```bash
   ls -la $OPENCLAW_WORKSPACE/.openclaw/bootstrap/session_context.md
   ```
3. **New session check:** verify the agent loads `session_context.md` when present (bootstrap preference works).
4. **After first weekly bridge run:** confirm rolling budget data exists — the legacy **`weekly_remaining_v1`** table may be empty while **`memory_records`** already holds the aggregate (modern path). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Use **`ainl status`** to verify the weekly budget line: **ainl status now shows the correct value via fallback** to **`memory_records`** when the legacy row is missing or null. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> You may still run the §Standard `sqlite3` checks on the legacy table (legacy table; modern data lives in memory_records). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
5. **After `run_intelligence.py` (non–dry-run):** confirm JSON includes `budget_hydrate` with `ok: true` when a rolling row exists (not permanently skipped).
6. **Monthly:** run `ainl bridge-sizing-probe --json` and tighten `AINL_BRIDGE_REPORT_MAX_CHARS` from evidence.

If any check fails, don’t broaden changes—fix the host contract first (bootstrap preference + shared workspace paths), then rerun.

---

### Optional: All-In-One Setup Script

Create `scripts/setup_ainl_integration.sh` in your workspace:

```bash
#!/usr/bin/env bash
set -euo pipefail

WS="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"

cat <<'JSON' | openclaw gateway config.patch - "$(date -u +"%Y-%m-%d %H:%M UTC") - Setup AINL integration"
{
  "env": {
    "vars": {
      "OPENCLAW_WORKSPACE": "'"$WS"'",
      "OPENCLAW_MEMORY_DIR": "'"$WS"'/memory",
      "OPENCLAW_DAILY_MEMORY_DIR": "'"$WS"'/memory",
      "AINL_FS_ROOT": "'"$WS"'",
      "AINL_MEMORY_DB": "'"$WS"'/.ainl/ainl_memory.sqlite3",
      "MONITOR_CACHE_JSON": "'"$WS"'/.ainl/monitor_state.json",
      "AINL_EMBEDDING_MEMORY_DB": "'"$WS"'/.ainl/embedding_memory.sqlite3",
      "AINL_IR_CACHE_DIR": "'"$WS"'/.cache/ainl/ir",
      "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": "true"
    }
  }
}
JSON

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

echo "AINL integration configured. Restart OpenClaw if needed."
```

Run it once after installing/upgrading AINL.

---

## 6. Expected outcomes (honest framing)

**Bootstrap (one-time, automated):** `ainl install-mcp --host openclaw` or `./install.sh` from the OpenClaw skill wires **`ainl-mcp`** into **`~/.openclaw/openclaw.json`**, installs the **`~/.openclaw/bin/ainl-run`** compile-then-run wrapper, and updates **PATH** hints—so the **toolchain** is ready without hand-editing MCP tables. **Bridge runners, cron payloads, and gateway caps** are **not** installed by that command alone; you still apply §2–§3 and the bridge docs (`openclaw/bridge/README.md`, `TOKEN_CAPS_STAGING.md`) so scheduled jobs and token-budget surfaces actually run.

**Self-managing with adaptive intelligence (v1.3.3 — resource & budget layer, not workflow logic):** After graphs are **compiled once**, AINL stays a **deterministic graph runtime**—it does **not** rewrite `.ainl` at runtime, mutate IR between runs, or do dynamic prompt optimization. What *does* adapt is the **surrounding ops layer**: the **cap auto-tuner** (`scripts/auto_tune_ainl_caps.py`, also `intelligence/auto_tune_ainl_caps.lang`; run via `python3 scripts/run_intelligence.py auto_tune_ainl_caps`) proposes **execution and report caps** from **observed** monitor/bridge/SQLite history; **`scripts/run_intelligence.py`** performs **rolling budget → `MONITOR_CACHE_JSON` hydration** (`budget_hydrate`) and runs startup-context / summarizer / consolidation programs; the **embedding retrieval pilot** (optional) indexes session summaries and can **shrink startup context** over time versus always loading full memory; **token-budget** bridges and adapters (weekly trends, rolling budget, sentinel-style guards documented in observability guides) support **auto-pruning and alerts** when usage exceeds thresholds; **`TOKEN_AND_USAGE_OBSERVABILITY.md`** ties **alerts and weekly trends** back into that loop. Together, this yields a **self-managing deployment** that **continuously optimizes resource usage and token budget** *after* compile—without replacing the compiled workflow itself.

**Token savings (benchmarked posture):** On **typical high-frequency monitoring and digest workflows**, with **strict mode** and **`minimal_emit`** where your artifact lane supports it, and with **host bootstrap + cron** wired as in this guide, measured economics often land in **~84–95%+** savings versus equivalent **prompt-loop orchestration** for the same scheduled work—**commonly 90–95%**—because **recurring runs carry near-zero orchestration-token cost** after the one-time compile, while **hydration, pruning, caps, and optional embeddings** keep **context and bridge payloads** bounded. **Session startup** alone is often **~85–92%** vs dumping full memory; the top of the band still assumes **validated** combinations (e.g. **WASM** for heavy deterministic steps, **embedding** pilot active, **tight gateway caps**). Treat percentages as **targets to validate** on your stack (`ainl bridge-sizing-probe`, weekly trends), not guarantees.

---

## 7. Common Pitfalls & Fixes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `weekly_remaining_v1` table not found | Schema not initialized (fresh DB) | Run `sqlite3 ~/.openclaw/workspace/.ainl/ainl_memory.sqlite3 \"CREATE TABLE IF NOT EXISTS weekly_remaining_v1 (week_start TEXT PRIMARY KEY, remaining_budget INTEGER, updated_at TEXT);\"` (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->) |
| Token Cost Tracker Telegram messages are empty or missing token counts | `IntelligenceReport` table missing or script error | Ensure `IntelligenceReport` table exists, check `~/.openclaw/logs/gateway.log` for errors. Re‑run: `python3 scripts/run_token_cost_tracker.py` |
| AINL cron jobs not running | Jobs not added or disabled | `openclaw cron list`; if missing, add with `openclaw cron add` using payloads from §3. |
| `session_context.md` not generated / full MEMORY loaded | `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` not set | Set to `true` in `openclaw.json` `env.shellEnv` and restart gateway. Verify via log grep. |
| “RPCWireError” from CodexBar CLI | CodexBar macOS app not running | Start CodexBar.app: `open -a CodexBar`. Ensure provider added in UI. |
| `ainl status` shows missing tables even after setup | Workspace path mismatch | Confirm `AINL_MEMORY_DB` path; ensure DB initialized at that location. |
| Embedding retrieval fails / “no such table: embedding_memory” | Embedding DB not created | Install embedding pilot (`EMBEDDING_RETRIEVAL_PILOT.md`) or set `AINL_EMBEDDING_MODE=stub`. |
| Caps not applied to cron jobs | Caps set via shell profile, jobs under Gateway | Use `env.shellEnv` in `openclaw.json` or wrap cron payloads to source profile. |
| Weekly trends job fails silently | `weekly_remaining_v1` missing or permission issue | Check logs; create table; ensure DB writable. (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->) |
| **`ainl status`** weekly budget still “Not initialized” but bridge ran | Legacy **`weekly_remaining_v1`** row empty; aggregate only in **`memory_records`** | Run **`ainl status`** again — it uses **`_read_weekly_remaining_rollup`** (legacy row first, else **`weekly_remaining_tokens`** from **`memory_records`**). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Confirm cap **`AINL_WEEKLY_TOKEN_BUDGET_CAP`** so remaining tokens can be computed. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> |
| Bridge report exceeds model’s context window | `AINL_BRIDGE_REPORT_MAX_CHARS` too high | Lower the cap or use a larger‑context model. |
| “Prompt too long” from provider | `PROMOTER_LLM_MAX_PROMPT_CHARS` too high | Reduce cap or use a model with larger context. |

---

## 8. Apollo's Working Configuration (Case Study)

This section documents a proven, production-ready setup that diverges slightly from the gold standard's profile emission approach while maintaining full AINL compliance and token savings.

### 7.1 Philosophy

Instead of using `eval "$(ainl profile emit-shell ...)"` to set environment caps globally, this configuration **keeps caps in `openclaw.json` under `env.shellEnv`**. The Gateway injects these variables when spawning agents and cron jobs, providing **scoped, upgrade-safe configuration** that requires no shell startup modifications.

### 7.2 Environment Caps (via `openclaw.json`)

```json
{
  "env": {
    "shellEnv": {
      "OPENCLAW_WORKSPACE": "/Users/clawdbot/.openclaw/workspace",
      "OPENCLAW_MEMORY_DIR": "/Users/clawdbot/.openclaw/workspace/memory",
      "OPENCLAW_DAILY_MEMORY_DIR": "/Users/clawdbot/.openclaw/workspace/memory",
      "AINL_FS_ROOT": "/Users/clawdbot/.openclaw/workspace/AI_Native_Lang",
      "AINL_MEMORY_DB": "/Users/clawdbot/.openclaw/workspace/.ainl/ainl_memory.sqlite3",
      "MONITOR_CACHE_JSON": "/Users/clawdbot/.openclaw/workspace/.ainl/monitor_state.json",
      "AINL_EMBEDDING_MEMORY_DB": "/Users/clawdbot/.openclaw/workspace/.ainl/embedding_memory.sqlite3",
      "AINL_IR_CACHE_DIR": "/Users/clawdbot/.openclaw/workspace/.cache/ainl/ir",
      "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": "true",
      "AINL_BRIDGE_REPORT_MAX_CHARS": "3132",
      "AINL_WEEKLY_TOKEN_BUDGET_CAP": "100000",
      "PROMOTER_LLM_MAX_PROMPT_CHARS": "4000",
      "PROMOTER_LLM_MAX_COMPLETION_TOKENS": "1000",
      "AINL_EXECUTION_MODE": "graph-preferred"
    }
  }
}
```

**Apply with:** `openclaw gateway config.patch <patch.json>` and restart the gateway.

### 7.3 Additional Tables (Beyond Default Schema)

The gold standard mentions `weekly_remaining_v1`. If not present, create it manually:

```sql
CREATE TABLE IF NOT EXISTS weekly_remaining_v1 (
  week_start TEXT PRIMARY KEY,
  remaining_budget INTEGER,
  updated_at TEXT
);
```

Run via: `sqlite3 ~/.openclaw/workspace/.ainl/ainl_memory.sqlite3 "CREATE TABLE ..."` (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->)

The `AINL Weekly Token Trends` cron job will populate this on its next run (Sundays 9 AM).

**Primary vs legacy:** Direct SQLite writes targeting only the legacy table are secondary; **real** rolling values flow **bridge → `memory_records`** (same logical key **`weekly_remaining_v1`**). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Install still creates the empty legacy table so older tooling and schema checks keep working. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

### 7.4 Project-Lock File (`aiNativeLang.yml`)

To make the setup reproducible and self-documenting, place `aiNativeLang.yml` at the workspace root:

```yaml
version: 1.0
project: "OpenClaw"
description: "OpenClaw integration with AINL — Apollo's configuration"
env:
  AINL_WEEKLY_TOKEN_BUDGET_CAP: 100000
  AINL_BRIDGE_REPORT_MAX_CHARS: 3132
  PROMOTER_LLM_MAX_PROMPT_CHARS: 4000
  PROMOTER_LLM_MAX_COMPLETION_TOKENS: 1000
  OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT: 1
  AINL_EXECUTION_MODE: "graph-preferred"
providers:
  - id: "openrouter"
    type: "factory"
    baseUrl: "https://openrouter.ai/api/v1"
    models:
      - id: "openrouter/stepfun/step-3.5-flash:free"
        name: "Step 3.5 Flash"
        contextWindow: 128000
        maxTokens: 8192
cron:
  - name: "AINL Context Injection"
    schedule: "*/5 * * * *"
  - name: "AINL Session Summarizer"
    schedule: "0 3 * * *"
  - name: "AINL Weekly Token Trends"
    schedule: "0 9 * * 0"
  - name: "Token Cost Tracker (AINL)"
    schedule: "0 * * * *"
memory:
  compaction:
    enabled: true
    reserveTokens: 50000
    keepRecentTokens: 40000
    maxHistoryShare: 0.65
    recentTurnsPreserve: 5
    memoryFlush:
      enabled: true
  dailyNotes: "memory/YYYY-MM-DD.md"
  longTerm: "MEMORY.md"
session:
  mode: "warn"
  maxEntries: 800
  pruneAfter: 30d
  parentForkMaxTokens: 100000
execution:
  mode: "graph-preferred"
  strictValidation: true
```

This file serves as **single-source truth** for the setup and is safe to commit to public repos (no secrets).

### 7.5 Cron Jobs (as managed by `openclaw cron`)

The following jobs are active and verified:

| Name | Schedule | Agent | Status |
|------|----------|-------|--------|
| AINL Context Injection | `*/5 * * * *` | main | ✅ |
| AINL Session Summarizer | `0 3 * * *` | main | ✅ |
| ainl-weekly-token-trends | `0 9 * * 0` | - | ✅ |
| Token Cost Tracker (AINL) | `0 * * * *` | main | ✅ |
| Session Budget Enforcement | `0 * * * *` | main | ✅ |
| AINL Proactive Monitor | `*/15 * * * *` | main | ✅ |
| ... and others | | | |

All jobs inherit the environment from the Gateway (`env.shellEnv`), ensuring caps apply consistently.

### 7.6 Provider Configuration

OpenRouter is configured as a **factory provider** in `openclaw.json`:

```json
{
  "providers": [
    {
      "id": "openrouter",
      "baseUrl": "https://openrouter.ai/api/v1",
      "apiKey": "...",
      "models": [
        { "id": "openrouter/stepfun/step-3.5-flash:free", ... },
        { "id": "openrouter/arcee-ai/trinity-large-preview:free", ... },
        // plus other free models; Claude Opus available but rarely used
      ]
    }
  ]
}
```

### 7.7 Token Savings Achieved

| Metric | Value |
|--------|-------|
| Total tokens processed (lifetime) | 10,501,100 |
| Input | 2,097,000 (20%) |
| Output | 8,404,100 (80%) |
| Actual cost | $0.00 (free tier) |
| Savings vs. Claude Opus (OpenRouter rates) | $220.59 |
| Savings vs. Claude Opus (Anthropic direct) | $661.77 |
| Additional efficiency gain from AINL (vs. prompt-loop) | ~2.5× token reduction → ~$300–$1000 saved |

### 7.8 Pros & Cons of This Approach

**Pros:**
- No shell profile modifications needed; works out of the box after Gateway restart.
- Caps are version-controlled alongside the rest of OpenClaw config.
- cron jobs and agents automatically pick up caps without wrapper scripts.
- Upgrade-safe: Gateway reads `openclaw.json` on every start; your caps persist.

**Cons:**
- Manual `ainl` CLI runs (outside Gateway) need a wrapper to export caps, or you must `eval` a generated profile.
- Not exactly matching the gold standard's `ainl profile emit-shell` method, though functionally equivalent for Gateway-managed processes.

### 7.9 Reproduction Steps for Other Hosts

1. Set the `env.shellEnv` keys in `openclaw.json` as shown in §7.2.
2. Create `weekly_remaining_v1` table if missing (SQL; legacy compatibility — **`ainl install openclaw`** bootstraps this too). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
3. Place `aiNativeLang.yml` at workspace root (optional but recommended).
4. Ensure cron jobs for AINL are present (use `openclaw cron add` or copy from §7.5).
5. Verify `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true` is set (it is in `shellEnv`).
6. Restart the Gateway: `openclaw gateway restart`.
7. Wait for the next weekly token trends run (Sunday 9 AM) to confirm data appears — either legacy **`weekly_remaining_v1`** rows and/or the **`memory_records`** aggregate (primary). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> **`ainl status`** should move off “Not initialized” for weekly budget once the aggregate exists (ainl status now shows correct value via fallback). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
8. Check that new sessions load `.openclaw/bootstrap/session_context.md` once generated.

This configuration is **fully compliant** with AINL v1.3.3 gold standard semantics, with only a **profile emission** deviation that is **safe and scoped**.

---

## Appendix A: Verification Commands

```bash
# Check that weekly_remaining_v1 exists (legacy table; modern data lives in memory_records)
sqlite3 ~/.openclaw/workspace/.ainl/ainl_memory.sqlite3 ".tables"
# (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->)

# Optional: latest rolling budget aggregate (memory_records — primary store for hydration / ainl status fallback)
sqlite3 ~/.openclaw/workspace/.ainl/ainl_memory.sqlite3 "SELECT updated_at, substr(payload_json,1,120) FROM memory_records WHERE namespace='workflow' AND record_kind='budget.aggregate' AND record_id='weekly_remaining_v1' ORDER BY updated_at DESC LIMIT 1;"
# (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->)

# List cron jobs
openclaw cron list

# Confirm env caps in running agents (check a recent job's log)
grep AINL_WEEKLY_TOKEN_BUDGET_CAP ~/.openclaw/logs/gateway.log | tail -1

# Verify session_context.md usage
ls -la ~/.openclaw/workspace/.openclaw/bootstrap/session_context.md
```

---

*End of Apollo's configuration case study.*

## Agent discovery

- **Machine-readable:** `tooling/bot_bootstrap.json` → **`openclaw_ainl_gold_standard`** (checklist) · **`openclaw_host_ainl_1_2_8`** (v1.2.8–v1.3.3 host briefing: repo vs host)
- **Hub:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) · [`docs/README.md`](../README.md) § operations · [`DOCS_INDEX.md`](../DOCS_INDEX.md)
- **OpenClaw requests 2–6 mapping:** [`OPENCLAW_REQUESTS_2_6_MAPPING.md`](OPENCLAW_REQUESTS_2_6_MAPPING.md) (what’s shipped through v1.3.3 vs proposed extensions; see doc header)
