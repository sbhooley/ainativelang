# Unified AINL + OpenClaw Monitoring Guide

**Scope:** OpenClaw bridge memory under **`~/.openclaw/workspace/`**, cron wrappers, and token-budget monitors. **OpenClaw MCP skill** (stdio **`ainl-mcp`**, **`openclaw.json`**) is separate: **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)**. **ZeroClaw** uses a different layout (**`~/.zeroclaw/`**, **`ainl install-zeroclaw`**); see **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)**.

**Audience:** operators who run OpenClaw cron, the AINL bridge runner, and daily markdown memory.

**Cross-links:** [`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md) (token budget deep dive) · [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md) (commands, env, cron patterns) · [`docs/CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md) (drift + registry + **`S` cron shape** + **notify/queue security**)

**Narrative:** [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents) — how **bridge daily markdown** relates to AINL’s tiered state and the SQLite **`memory`** adapter ([`docs/adapters/MEMORY_CONTRACT.md`](../adapters/MEMORY_CONTRACT.md)).

---

## Architecture overview

The **OpenClaw bridge** (`openclaw/bridge/`) is the supported integration layer between OpenClaw cron/shell and AINL graphs: **`run_wrapper_ainl.py`** loads registered wrappers (e.g. **`token-budget-alert`**, **`weekly-token-trends`**), runs **`RuntimeEngine`** with the OpenClaw monitor registry, and coordinates adapters:

- **`openclaw_memory`** — append/read **daily markdown** at **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**
- **`bridge`** (`BridgeTokenBudgetAdapter`) — token-usage JSON subprocess, cache **stat** / **prune**, notify queue assembly
- **`queue`** — single consolidated **notify** put (live) for Telegram / OpenClaw delivery
- **`core`** — timestamps (`R core now`), string ops, guards

**Token budget system:** The daily wrapper produces a **`## Token Usage Report`** in memory, optional **`## Cache Prune`**, and (live) one outbound **Daily AINL Status** message when there is anything to say. A **sentinel file** stops duplicating the **main** report on the same UTC calendar day.

**Weekly trends:** A separate wrapper scans recent daily `*.md` files and appends **`## Weekly Token Trends`**.

Canonical language/compiler/runtime semantics are unchanged; see **`docs/AINL_CANONICAL_CORE.md`** § *OpenClaw Bridge Layer*.

```text
OpenClaw cron / manual shell
        │
        ▼
openclaw/bridge/run_wrapper_ainl.py  <─── wrapper name
        │
        ├─► openclaw_memory  ──►  ~/.openclaw/workspace/memory/YYYY-MM-DD.md
        ├─► bridge             ──►  token-usage, cache stat/prune, notify queue
        ├─► queue (notify)     ──►  Telegram / OpenClaw (live only)
        └─► core               ──►  UTC header timestamp, guards
```

---

## Key locations

| Artifact | Default path | Override |
|----------|--------------|----------|
| Daily OpenClaw markdown | **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** | `OPENCLAW_MEMORY_DIR`, `OPENCLAW_DAILY_MEMORY_DIR`, or `OPENCLAW_WORKSPACE` |
| Monitor / search cache JSON | **`/tmp/monitor_state.json`** | `MONITOR_CACHE_JSON` |
| Sentinel (main report duplicate guard) | **`/tmp/token_report_today_sent`** (contains one line `YYYY-MM-DD`, UTC) | `AINL_TOKEN_REPORT_SENTINEL` |

Verify paths:

```bash
ls -la ~/.openclaw/workspace/memory/$(date -u +%Y-%m-%d).md
ls -la "${MONITOR_CACHE_JSON:-/tmp/monitor_state.json}"
ls -la "${AINL_TOKEN_REPORT_SENTINEL:-/tmp/token_report_today_sent}"
```

---

## Daily token budget alert

**Runner:** `python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert`  
**Declared cron in source:** **`0 23 * * *`** (23:00 UTC daily) — keep OpenClaw jobs in sync.

**What it monitors**

- Estimated token usage vs **`AINL_ADVOCATE_DAILY_TOKEN_BUDGET`** (default **500000** unless set).
- **`MONITOR_CACHE_JSON`** file size: **> 10 MB** drops **`cache_ok`** (budget line may be omitted from chat); **> 15 MB** can add a **critical cache** notify line; **> 12 MB** triggers **`monitor_cache_prune auto`** after the report path.

**When it alerts (live)**

- **Consolidated** `R queue Put` only if at least one line was queued: critical cache, prune success (if keys removed), and/or budget warning (only if **`budget_warning`** and **`cache_ok`**).

**Detail:** [`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md)

---

## Weekly token trends

**Runner:** `python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends`  
**Declared cron in source:** **`0 9 * * 0`** — Sunday **09:00 UTC**.

Scans up to **14** recent `YYYY-MM-DD.md` files under the memory directory, parses **`## Token Usage Report`** sections, and appends **`## Weekly Token Trends`** to **today’s** file (live). Use **`--dry-run`** to validate without writing.

---

## ZeroClaw bridge monitoring

**ZeroClaw** uses **`zeroclaw/bridge/`** (not **`openclaw/bridge/`**): **`zeroclaw-ainl-run`** or **`python3 zeroclaw/bridge/run_wrapper_ainl.py`**, with daily notes under **`~/.zeroclaw/workspace/memory/`** (override with **`ZEROCLAW_WORKSPACE`** / **`ZEROCLAW_MEMORY_DIR`**). The production wrappers **`token-budget-alert`**, **`weekly-token-trends`**, and **`monthly-token-summary`** append reports to **today’s** note on live runs and enqueue a short outbound notify routed by **`ZEROCLAW_NOTIFY_TARGET`**.

**JSON stdout (ZeroClaw runner only):** prints **`{"status": "ok", "out": …, "wrapper": …}`** on **`--dry-run`** or when **`--json`** / **`--output=json`** is set; add **`--pretty`** for indented JSON. **Live** runs omit stdout by default (unlike **`openclaw/bridge/run_wrapper_ainl.py`**, which always prints a JSON envelope with **`"ok": true`**).

At-a-glance cadence, cron hints, and notify prefixes: **[`docs/ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md#cadence-overview)**.

---

## Cron jobs

Set **`AINL_WORKSPACE`** to your AINL repo root (see [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)).

**Daily token budget (23:00 UTC):**

```bash
openclaw cron add \
  --name ainl-token-budget-alert \
  --cron "0 23 * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert' \
  --description "AINL daily token usage, prune, consolidated notify"
```

**Weekly trends (Sunday 09:00 UTC):**

```bash
openclaw cron add \
  --name ainl-weekly-token-trends \
  --cron "0 9 * * 0" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends' \
  --description "AINL weekly token trends markdown append"
```

Staging: insert **`--dry-run`** immediately before the wrapper name in the payload when you need zero memory writes.

After changes, run **`python3 openclaw/bridge/cron_drift_check.py`** and follow [`docs/CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md).

---

## Environment variables reference

| Name | Default (typical) | Purpose |
|------|-------------------|---------|
| `OPENCLAW_MEMORY_DIR` / `OPENCLAW_DAILY_MEMORY_DIR` | (unset → under `~/.openclaw/workspace/memory/`) | Directory for `YYYY-MM-DD.md` |
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | Parent for `memory/` when dir envs unset |
| `MONITOR_CACHE_JSON` | `/tmp/monitor_state.json` | Token monitor / search cache path |
| `AINL_ADVOCATE_DAILY_TOKEN_BUDGET` | `500000` | Denominator for budget % in token-usage |
| `AINL_TOKEN_PRUNE_DAYS` | (unset → **60** in `auto` prune) | Age threshold (days) for prune |
| `AINL_TOKEN_REPORT_SENTINEL` | `/tmp/token_report_today_sent` | Duplicate-guard file for main daily report |
| `AINL_DRY_RUN` | — | Frame/env dry run when set (prefer `--dry-run` on CLI) |
| `AINL_BRIDGE_FAKE_CACHE_MB` | — | **Test:** fake cache size (MB) |
| `AINL_BRIDGE_PRUNE_FORCE_ERROR` | — | **Test:** simulate prune error |
| `OPENCLAW_BIN` | `openclaw` on PATH | CLI for memory / notify subprocesses |
| `OPENCLAW_TARGET`, `OPENCLAW_NOTIFY_CHANNEL` | install-specific | Notify routing |

---

## Monitoring commands

```bash
# Daily wrapper — no live append / no queue / no sentinel (main report)
python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run

# Weekly trends — dry run
python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends --dry-run

# Token usage JSON only (scripts)
python3 openclaw/bridge/ainl_bridge_main.py token-usage --dry-run --json-output

# Cron drift (read-only)
python3 openclaw/bridge/cron_drift_check.py
```

**Inspect memory / cache from shell:**

```bash
tail -n 80 ~/.openclaw/workspace/memory/$(date -u +%Y-%m-%d).md
grep -E "Token Usage|Cache Prune|Weekly Token" ~/.openclaw/workspace/memory/*.md | tail -20
ls -la "${MONITOR_CACHE_JSON:-/tmp/monitor_state.json}"
```

---

## Troubleshooting & tuning

**Reset sentinel** (allow one more **live** main report today):

```bash
rm -f /tmp/token_report_today_sent
# or: rm -f "$AINL_TOKEN_REPORT_SENTINEL"
```

**Fake cache testing:** `AINL_BRIDGE_FAKE_CACHE_MB=16` with **`--dry-run`** — see [`BRIDGE_TOKEN_BUDGET_ALERT.md`](../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md).

**Telegram / queue silent:** Ensure not dry-run; check `OPENCLAW_*` env; remember budget line requires cache **≤ 10 MB**.

**Threshold / schedule changes:** Edit `openclaw/bridge/wrappers/token_budget_alert.ainl` (and weekly wrapper if needed), update **`tooling/cron_registry.json`** and OpenClaw jobs, then **`cron_drift_check.py`**.

| Threshold | Behavior |
|-----------|-----------|
| Cache **> 10 MB** | `cache_ok = 0`; budget line typically omitted from consolidated notify |
| Cache **> 12 MB** | `monitor_cache_prune auto` after report path |
| Cache **> 15 MB** | Extra **critical cache** notify line (live) |

---

## Cross-links

- **[`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md)** — overview, sentinel, env vars, sample output, troubleshooting
- **[`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)** — monitoring tools table, **Scheduled reporting & alerting**, `AINL_WORKSPACE` patterns
- **[`docs/ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)** — ZeroClaw bridge, **`zeroclaw-ainl-run`**, monthly wrapper, **`ZEROCLAW_NOTIFY_TARGET`**, JSON CLI flags
- **[`docs/CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md)** — drift checks, `openclaw/bridge/wrappers/` note
- **[`docs/ainl_openclaw_unified_integration.md`](../ainl_openclaw_unified_integration.md)** — integration boundaries and env vars

---

**Checklist:** [ ] Memory path **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** · [ ] Dry-run before live cron · [ ] Sentinel understood · [ ] Drift check after schedule/payload edits
