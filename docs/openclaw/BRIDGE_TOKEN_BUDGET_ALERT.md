# Bridge Token Budget Alert System

**See also:** [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md) (runner, monitoring table, cron snippets) · [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md) (full stack: weekly trends, cron, env reference, drift)

---

## Overview

The **token budget alert** is a scheduled OpenClaw bridge workflow (`openclaw/bridge/wrappers/token_budget_alert.ainl`, runner name **`token-budget-alert`**). In production it:

- Appends a daily **`## Token Usage Report`** (and related markdown) to OpenClaw’s dated markdown log — see **Memory location** below.
- Surfaces **budget pressure** when estimated usage crosses the configured warning threshold (relative to `AINL_ADVOCATE_DAILY_TOKEN_BUDGET`), and can include a **budget warning** line in a **single consolidated** outbound notify message (Telegram / OpenClaw queue), when cache size allows.
- Measures the **monitor search cache** (`MONITOR_CACHE_JSON`) via `R bridge monitor_cache_stat`; if the file is **critically large**, it can queue a **critical cache** line in the same consolidated message.
- Optionally runs **`monitor_cache_prune auto`** when the cache exceeds **12 MB** (by file size), then appends a **`## Cache Prune`** markdown block (success or error) to memory — **self-healing** without spamming multiple chat messages.

**One consolidated alert:** On **live** runs, the graph queues notify lines internally, then performs **one** `R queue Put` at the end. The first line is timestamped in UTC: **`Daily AINL Status - <timestamp from R core now>`**. Body lines may combine cache critical, prune success, and/or budget warning (budget text only when **`cache_ok`** — cache **≤ 10 MB**).

---

## How it works

1. **Schedule (documentation / drift source):** `S core cron "0 23 * * *"` — **23:00 UTC daily** in the wrapper source. Production timing is whatever you configure in OpenClaw (`openclaw cron add`); keep it aligned with [`docs/CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md) and `tooling/cron_registry.json`.

2. **Invocation:**

   ```bash
   python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert [--dry-run]
   ```

3. **Sentinel duplicate guard (live only):** After a successful main report append, the bridge records today’s UTC date in a small sentinel file (default **`/tmp/token_report_today_sent`**) via `token_report_today_sent` / `token_report_today_touch`. If the same UTC day is seen again, the **main** `## Token Usage Report` append is **skipped** so repeated manual runs do not duplicate the full block. **`AINL_TOKEN_REPORT_SENTINEL`** overrides the path. **`--dry-run`** does **not** write the sentinel and does **not** append the main report.

4. **Consolidated notify:** Built by `token_budget_notify_*` helpers; header uses **`R core now`** formatted in UTC. Delivery is **`R queue Put`** (live only; skipped when `dry_run`).

5. **Adapter surface:** `R bridge monitor_cache_stat`, `token_budget_warn`, `token_budget_report`, `token_budget_notify_*`, `monitor_cache_prune` — implemented in **`openclaw/bridge/bridge_token_budget_adapter.py`** so paths under `/tmp` work even when the sandboxed **`fs`** adapter cannot read them.

---

## Memory location

Live appends go to OpenClaw **daily markdown**:

**`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**

Override the directory (not the date in the filename) with **`OPENCLAW_MEMORY_DIR`** or **`OPENCLAW_DAILY_MEMORY_DIR`**, or derive from **`OPENCLAW_WORKSPACE`** — same rules as `openclaw_memory` / [`docs/ainl_openclaw_unified_integration.md`](../ainl_openclaw_unified_integration.md).

**Quick check:**

```bash
ls -la ~/.openclaw/workspace/memory/$(date -u +%Y-%m-%d).md
grep -n "Token Usage Report" ~/.openclaw/workspace/memory/$(date -u +%Y-%m-%d).md
```

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `AINL_TOKEN_PRUNE_DAYS` | When set (integer ≥ 1), used as `days_old` for `monitor_cache_prune auto`. Otherwise bridge default is **60** days. |
| `AINL_BRIDGE_FAKE_CACHE_MB` | **Tests / diagnostics only:** float — pretend the monitor cache is this many MB so you can exercise **>10 / >12 / >15 MB** branches without a huge real `MONITOR_CACHE_JSON`. |
| `AINL_BRIDGE_PRUNE_FORCE_ERROR` | **Tests only:** `1` / `true` / `yes` — force a synthetic prune **error** payload (no real file changes in dry-run). |
| `AINL_TOKEN_REPORT_SENTINEL` | Path to the duplicate-guard file storing today’s `YYYY-MM-DD`. Default **`/tmp/token_report_today_sent`**. |

Additional variables used alongside this workflow (notify, memory dir, cache path, budget) are tabulated with defaults in **[`docs/operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md)** § *Environment variables reference*.

---

## Example report output

The following is a **representative** markdown block as appended under **`## Token Usage Report`** (exact numbers and lines depend on your cache and history):

```markdown
## Token Usage Report
- Estimated tokens (rolling window): 412000
- Daily budget: 500000
- Budget used: 82.4%
- Budget warning: yes (≥ 80% of daily budget)
- Monitor cache file: /tmp/monitor_state.json
- Monitor cache size: 2.1 MB
- Sources: MONITOR_CACHE_JSON, recent daily markdown
```

A separate **`## Cache Prune`** section may appear after a prune branch runs, for example:

```markdown
## Cache Prune
- Removed 12 old entries
- New size: 3.2140 MB
```

**Example consolidated Telegram-style payload (live):**

```text
Daily AINL Status - 2026-03-20 14:32:01 UTC
Token budget warning: 85.0% used | Cache: 2.1 MB | See ~/.openclaw/workspace/memory/2026-03-20.md
```

---

## Troubleshooting

| Issue | What to do |
|-------|------------|
| **Duplicate full report same UTC day** | Expected: sentinel blocks the second main append. To force **one** more live append, remove the sentinel: `rm -f /tmp/token_report_today_sent` (or your `AINL_TOKEN_REPORT_SENTINEL`). |
| **Simulate large cache without a huge file** | `AINL_BRIDGE_FAKE_CACHE_MB=16 python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run` — inspect stdout JSON `out` for prune / warning branches. Remove before production cron. |
| **No Telegram / queue message** | Confirm **no** `--dry-run`; confirm `OPENCLAW_BIN`, `OPENCLAW_TARGET`, `OPENCLAW_NOTIFY_CHANNEL` match your other monitors; note that an **empty** notify queue sends nothing. If cache **> 10 MB**, the **budget** line may be omitted from the consolidated message while critical/prune lines can still fire. |
| **Prune never runs** | Prune triggers only when `monitor_cache_stat` reports **> 12 MB**. Check `MONITOR_CACHE_JSON` points at the real file: `ls -la "${MONITOR_CACHE_JSON:-/tmp/monitor_state.json}"`. |
| **Nothing in daily markdown** | Run live (no `--dry-run`); verify `OPENCLAW_MEMORY_DIR` and permissions on **`~/.openclaw/workspace/memory/`**. |

Dry-run smoke test (no disk notify, no live sentinel for main report):

```bash
python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run
```

---

## Cross-links

- **[`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)** — `run_wrapper_ainl.py`, monitoring tools table, env vars, **Scheduled reporting & alerting**
- **[`docs/operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md)** — architecture, weekly trends, full cron payloads, sentinel deep dive, tuning thresholds
- **[`docs/CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md)** — registry and `cron_drift_check.py`
- Wrapper source: `openclaw/bridge/wrappers/token_budget_alert.ainl` · Weekly companion: `openclaw/bridge/wrappers/weekly_token_trends.ainl` (documented in the unified guide)
