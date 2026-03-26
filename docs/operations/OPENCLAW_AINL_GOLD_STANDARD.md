# OpenClaw + AINL — gold standard (install / upgrade)

**Purpose:** Canonical reference for **agents and operators** after **`pip install`** / **`ainl install-mcp --host openclaw`** (or similar). Follow this to align **profiles**, **caps**, **cron**, **shared paths**, and **verification** so token savings and **`budget_hydrate`** behavior show up in real sessions. **Adapt numbers** to your measured workload (`bridge-sizing-probe`); the structure stays the same.

**AINL v1.2.8 host briefing (what the repo ships vs what OpenClaw must do):** [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md) — copy-paste ready for operators; **`tooling/bot_bootstrap.json`** → **`openclaw_host_ainl_1_2_8`**.

**See also:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) (bundle index) · [`AINL_PROFILES.md`](AINL_PROFILES.md) · [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) · [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`../INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md) · [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) · [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)

---

## 0. Prerequisites

- OpenClaw installed and running
- AINL repository cloned and available at `$WORKSPACE/AI_Native_Lang`
- `ainl` CLI in PATH (from AINL install)

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
4. **After first weekly bridge run:** confirm `weekly_remaining_v1` exists in SQLite.
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

**Self-managing with adaptive intelligence (v1.2.8 — resource & budget layer, not workflow logic):** After graphs are **compiled once**, AINL stays a **deterministic graph runtime**—it does **not** rewrite `.ainl` at runtime, mutate IR between runs, or do dynamic prompt optimization. What *does* adapt is the **surrounding ops layer**: the **cap auto-tuner** (`scripts/auto_tune_ainl_caps.py`, also `intelligence/auto_tune_ainl_caps.lang`; run via `python3 scripts/run_intelligence.py auto_tune_ainl_caps`) proposes **execution and report caps** from **observed** monitor/bridge/SQLite history; **`scripts/run_intelligence.py`** performs **rolling budget → `MONITOR_CACHE_JSON` hydration** (`budget_hydrate`) and runs startup-context / summarizer / consolidation programs; the **embedding retrieval pilot** (optional) indexes session summaries and can **shrink startup context** over time versus always loading full memory; **token-budget** bridges and adapters (weekly trends, rolling budget, sentinel-style guards documented in observability guides) support **auto-pruning and alerts** when usage exceeds thresholds; **`TOKEN_AND_USAGE_OBSERVABILITY.md`** ties **alerts and weekly trends** back into that loop. Together, this yields a **self-managing deployment** that **continuously optimizes resource usage and token budget** *after* compile—without replacing the compiled workflow itself.

**Token savings (benchmarked posture):** On **typical high-frequency monitoring and digest workflows**, with **strict mode** and **`minimal_emit`** where your artifact lane supports it, and with **host bootstrap + cron** wired as in this guide, measured economics often land in **~84–95%+** savings versus equivalent **prompt-loop orchestration** for the same scheduled work—**commonly 90–95%**—because **recurring runs carry near-zero orchestration-token cost** after the one-time compile, while **hydration, pruning, caps, and optional embeddings** keep **context and bridge payloads** bounded. **Session startup** alone is often **~85–92%** vs dumping full memory; the top of the band still assumes **validated** combinations (e.g. **WASM** for heavy deterministic steps, **embedding** pilot active, **tight gateway caps**). Treat percentages as **targets to validate** on your stack (`ainl bridge-sizing-probe`, weekly trends), not guarantees.

---

## Agent discovery

- **Machine-readable:** `tooling/bot_bootstrap.json` → **`openclaw_ainl_gold_standard`** (checklist) · **`openclaw_host_ainl_1_2_8`** (v1.2.8 host briefing: repo vs host)
- **Hub:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) · [`docs/README.md`](../README.md) § operations · [`DOCS_INDEX.md`](../DOCS_INDEX.md)
- **OpenClaw requests 2–6 mapping:** [`OPENCLAW_REQUESTS_2_6_MAPPING.md`](OPENCLAW_REQUESTS_2_6_MAPPING.md) (what’s shipped in v1.2.8 vs proposed extensions)
