# OpenClaw bridge (`openclaw/bridge/`)

This directory holds **OpenClaw-specific** helpers: cron runners, drift checks, memory CLI, and thin triggers. They are **not** part of AINL canonical core (see `docs/AINL_CANONICAL_CORE.md`).

## Calling AINL from OpenClaw, agents, or OS cron

1. **Preferred:** run the bridge runner with a registered wrapper name (or `full-unification` for the example):

   ```bash
   cd /path/to/AI_Native_Lang
   python3 openclaw/bridge/run_wrapper_ainl.py supervisor --dry-run
   python3 openclaw/bridge/run_wrapper_ainl.py full-unification --dry-run
   ```

2. **Shell-friendly alias:** `trigger_ainl_wrapper.py` forwards argv to the same runner (handy for short cron lines):

   ```bash
   python3 openclaw/bridge/trigger_ainl_wrapper.py content-engine --dry-run
   ```

3. **Legacy paths:** `scripts/run_wrapper_ainl.py`, `scripts/cron_drift_check.py`, and `scripts/ainl_memory_append_cli.py` are thin shims that delegate here so existing docs and fingerprints keep working.

`--dry-run` sets `frame["dry_run"]` and `AINL_DRY_RUN` so adapters avoid network and disk side effects while the graph still executes.

## Wrapper graphs under `wrappers/*.ainl`

Cron wrappers in this folder are compiled like any other AINL file from their **on-disk path**:

- **`include`** paths are resolved **relative to the wrapper file**. Files under `openclaw/bridge/wrappers/` should use relative paths such as **`../../modules/common/...`** to reach shared `modules/common` graphs, not bare `modules/...` (that only works when the wrapper lives at the repo root).
- Prefer **`R fs read "<path>"`** plus string ops (e.g. **`core.split`**) over verbs that are not on the **`fs`** contract for your runner.
- Multi-branch **`If`** uses **two** label targets (then / else); a single-label `If` is invalid.

Example maintenance: **`wrappers/token_aware_startup_context.ainl`** (token budget cron).

## Recommended OpenClaw cron commands (`--session-key agent:default:ainl-advocate`)

Use your workspace path and keep payloads stable so `tooling/cron_registry.json` fingerprints still match after `openclaw cron add`:

```bash
openclaw cron add \
  --name ainl-supervisor \
  --cron "*/15 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'Run: cd /ABS/PATH/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py supervisor'

openclaw cron add \
  --name ainl-content-engine \
  --cron "*/30 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'Run: cd /ABS/PATH/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py content-engine'
```

Adjust `--cron` to match `modules/openclaw/cron_*.ainl` and `tooling/cron_registry.json`.

## `daemon.sh` in parallel (long-lived + cron)

- Run **one** Advocate / gateway `daemon.sh` per role (or use process supervision). Do not stack duplicate daemons on the same socket or same CRM port without distinct config.
- **Parallel with bridge:** OpenClaw cron invokes short-lived `python3 ... run_wrapper_ainl.py ...` processes; they exit after each tick. That is safe alongside a long-running `daemon.sh` as long as ports, workspace paths, and env vars (`CRM_API_BASE`, `OPENCLAW_MEMORY_DIR`) are consistent.
- Prefer `--dry-run` in staging; use `openclaw/bridge/cron_drift_check.py` after changing schedules or job text.

## Other helpers

| Script | Role |
|--------|------|
| `cron_drift_check.py` | Read-only compare: registry vs AINL IR vs `openclaw cron list --json` |
| `ainl_memory_append_cli.py` | Append one line to daily OpenClaw markdown via `openclaw_memory` |
| `sync_node_to_ainl_memory.py` | Pipe or argv → same append (for Node/shell glue) |
| `token_usage_reporter.py` | CLI `token-usage`: token/budget summary → stdout + optional `openclaw_memory` append |
| `bridge_token_budget_adapter.py` | `R bridge token_budget_*` for `token_budget_alert.ainl` (subprocesses `token-usage --json-output`) |
| `wrappers/token_budget_alert.ainl` | Daily digest; one consolidated `R queue Put` (live); `monitor_cache_prune auto` + markdown when cache >12MB; env `AINL_TOKEN_PRUNE_DAYS`; tests: `AINL_BRIDGE_FAKE_CACHE_MB`, `AINL_BRIDGE_PRUNE_FORCE_ERROR` |
| `wrappers/weekly_token_trends.ainl` | Sunday-style weekly summary: bridge scans last 7–14 daily `memory/*.md` files, parses `## Token Usage Report`, appends `## Weekly Token Trends`, then `rolling_budget_publish` → `workflow`/`budget.aggregate`/`weekly_remaining_v1` (dry-run safe) |
| `wrappers/ttl_memory_tuner.ainl` | Weekly TTL adjustments for `workflow` rows whose metadata `tags` include `ttl_managed` (see `bridge_token_budget_adapter.ttl_memory_tuner_run`) |
| `wrappers/embedding_memory_pilot.ainl` | Pilot: index SQLite memory → **`embedding_memory`**, top-k search + optional daily md line (`embedding_workflow_index` / `embedding_workflow_search`) |
| `ir_cache.py` | Wrapper compile cache for `run_wrapper_ainl.py` (`AINL_IR_CACHE`, `AINL_IR_CACHE_DIR`) |

See `docs/ainl_openclaw_unified_integration.md` and `docs/CRON_ORCHESTRATION.md` for full integration context. **Unified operator guide (memory path, sentinel, cron, troubleshooting):** `docs/operations/UNIFIED_MONITORING_GUIDE.md`.

### Token tracker adapter (`openclaw_token_tracker`)

Registered in **`build_wrapper_registry()`** for AINL programs that invoke **`R openclaw_token_tracker ...`** (`RUN`, `ReadTokenStats`). Aggregates **`agent:main:main`** session tokens via **`openclaw sessions --json --active`**, optional **`openclaw cache`** read/write.

| Variable | Default | Role |
|----------|---------|------|
| `OPENCLAW_BIN` | (see `adapters/openclaw_token_tracker.py`) | `openclaw` CLI used for `sessions` / `cache` |
| `TOKEN_TRACKER_CACHE_NS` | `workflow` | Cache namespace for snapshots |
| `TOKEN_TRACKER_CACHE_KEY` | `main_session_tokens` | Cache key |
| `TOKEN_TRACKER_WINDOW_MINUTES` | `60` | `--active` window for `sessions` |
| `TOKEN_TRACKER_CACHE_TTL` | `300` | Fresh-cache TTL for `ReadTokenStats` (seconds) |

Full narrative: [`docs/ainl_openclaw_unified_integration.md`](../../docs/ainl_openclaw_unified_integration.md) (Token tracker + content-engine budget).

### Content-engine and wrapper budget guards

**`content-engine`** reads optional **`model_override`** from monitor **`cache`** (`budget` / `model_override`); otherwise uses **`gpt-4o-mini`**. It is a **critical** wrapper: when **`MONITOR_CACHE_JSON`** reports low **`workflow.token_budget`**, the bridge **skips non-critical wrappers** only—**`content-engine`** and **`token-budget-alert`** still run. Tune **`AINL_WRAPPER_MIN_DAILY_REMAINING`**, **`AINL_WRAPPER_MIN_WEEKLY_REMAINING`**, **`AINL_WRAPPER_BUDGET_GUARDS_JSON`** in `run_wrapper_ainl.py`.

### Monitoring tools (production)

Daily markdown target (unless overridden): **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**. Detail: `docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`.

| Tool / wrapper | Typical command | Role |
|----------------|-----------------|------|
| `token-budget-alert` | `python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert` | Daily token report append, optional **consolidated** notify (timestamped `Daily AINL Status - … UTC`), cache stat/prune, **sentinel** duplicate guard for main report |
| `weekly-token-trends` | `python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends` | Sunday-style scan of recent daily `*.md` → append **`## Weekly Token Trends`** + rolling budget aggregate row |
| `ttl-memory-tuner` | `python3 openclaw/bridge/run_wrapper_ainl.py ttl-memory-tuner` | Adjust TTL on tagged workflow memory rows (weekly) |
| `embedding-memory-pilot` | `python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot` | Index `workflow` memory into **`embedding_memory`**, top-k search + optional daily md append (pilot) |
| `token-usage` | `python3 openclaw/bridge/ainl_bridge_main.py token-usage` | Ad-hoc report to stdout; optional append (see flags); `--json-output` for wrappers |
| `cron_drift_check.py` | `python3 openclaw/bridge/cron_drift_check.py` | Read-only: registry vs IR vs `openclaw cron list` |
| `ainl_memory_append_cli.py` | `python3 openclaw/bridge/ainl_memory_append_cli.py "line"` | Manual one-line append to today’s OpenClaw markdown |
| `supervisor` | `python3 openclaw/bridge/run_wrapper_ainl.py supervisor` | **Source graph:** `scripts/wrappers/supervisor_fixed.ainl` (see `WRAPPERS["supervisor"]` in `run_wrapper_ainl.py`). Uses canonical **`R openclaw_memory append_today`** for daily markdown append — keep this form when editing copy-paste cron payloads. |

#### OpenSpace / MCP dev smoke

- **Wrapper name `test-openspace-mcp`:** `python3 openclaw/bridge/run_wrapper_ainl.py test-openspace-mcp --dry-run` — loads **`demo/test_openspace_mcp.ainl`** (HTTP MCP **`execute_task`**; demo tree, not strict-valid CI).
- **Repo-root harness:** `python3 run_openspace_test.py` — same demo graph with **`openclaw_monitor_registry()`** for quick adapter/registry smoke (paths resolved from repo root).

#### Environment variables (monitoring)

| Variable | Role |
|----------|------|
| `OPENCLAW_MEMORY_DIR` / `OPENCLAW_DAILY_MEMORY_DIR` | Directory for `YYYY-MM-DD.md` (default under `~/.openclaw/workspace/memory/`) |
| `OPENCLAW_WORKSPACE` | Parent for `memory/` when explicit dir not set |
| `MONITOR_CACHE_JSON` | Token monitor cache file used by stat/prune/report |
| `AINL_TOKEN_PRUNE_DAYS` | Age threshold for `monitor_cache_prune auto` (else **60** days) |
| `AINL_TOKEN_REPORT_SENTINEL` | Duplicate-guard file path (default `/tmp/token_report_today_sent`) |
| `AINL_DRY_RUN` / `--dry-run` | Skip live `append_today`, queue notify, sentinel, prune file writes |
| `AINL_BRIDGE_FAKE_CACHE_MB`, `AINL_BRIDGE_PRUNE_FORCE_ERROR` | **Tests only** — branch simulation |
| `OPENCLAW_BIN`, `OPENCLAW_TARGET`, `OPENCLAW_NOTIFY_CHANNEL` | Notify / CLI integration; **`OPENCLAW_BIN`** also drives **`openclaw_token_tracker`** |
| `TOKEN_TRACKER_CACHE_NS`, `TOKEN_TRACKER_CACHE_KEY`, `TOKEN_TRACKER_WINDOW_MINUTES`, `TOKEN_TRACKER_CACHE_TTL` | Token tracker adapter cache + sessions window (see § Token tracker adapter) |
| `AINL_WRAPPER_MIN_DAILY_REMAINING`, `AINL_WRAPPER_MIN_WEEKLY_REMAINING`, `AINL_WRAPPER_BUDGET_GUARDS_JSON` | Skip **non-critical** wrappers when budgets low; **`content-engine`** is critical |
| `AINL_ADVOCATE_DAILY_TOKEN_BUDGET` | Budget denominator for token-usage (default 500000) |
| `AINL_IR_CACHE` | `0` disables IR disk cache for `run_wrapper_ainl.py` (default on) |
| `AINL_IR_CACHE_DIR` | Cache directory (default `~/.cache/ainl/ir`) |
| `AINL_WEEKLY_TOKEN_BUDGET_CAP` | Optional weekly token cap; `rolling_budget_publish` stores `weekly_remaining_tokens` |
| `AINL_TTL_TUNER_TAG` | Metadata tag required for TTL tuning (default `ttl_managed`) |
| `AINL_BRIDGE_REPORT_MAX_CHARS` | If set (>0), caps **`token_budget_report`** markdown; overflow → short “budget exhausted” stub |
| `AINL_EMBEDDING_INDEX_NAMESPACE` | For **`embedding_workflow_index`**: memory namespace to scan (default `workflow`) |
| `AINL_EMBEDDING_MEMORY_DB` / `AINL_EMBEDDING_MODE` | Sidecar index path and stub vs OpenAI embeddings (`adapters/embedding_memory.py`) |

**Sizing (report cap + embedding namespace):** `ainl bridge-sizing-probe` (or `ainl-bridge-sizing-probe`, or `python3 scripts/bridge_sizing_probe.py`), then see **Sizing checklist** in [`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](../../docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md).

### Weekly token trends (Sunday example)

```bash
openclaw cron add \
  --name ainl-weekly-token-trends \
  --cron "0 9 * * 0" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends'
```

Use `--dry-run` in the message while validating; remove it for live appends to today’s memory file.

## Recommended OpenClaw cron patterns (`$AINL_WORKSPACE`)

Set once in your shell profile or OpenClaw environment so payloads stay portable:

```bash
export AINL_WORKSPACE=/path/to/AI_Native_Lang
```

Then schedule with a **single** working-directory hop (shell expands `$AINL_WORKSPACE` when you add the job):

```bash
openclaw cron add \
  --name ainl-supervisor \
  --cron "*/15 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && python3 openclaw/bridge/run_wrapper_ainl.py supervisor'
```

Use the same pattern for `content-engine`, `github-intelligence`, etc. Keep the substring `run_wrapper_ainl.py` stable if your `tooling/cron_registry.json` fingerprints depend on it.

## Using the central bridge entrypoint (`ainl_bridge_main.py`)

One dispatcher, same behavior as calling the individual scripts:

```bash
cd /path/to/AI_Native_Lang
python3 openclaw/bridge/ainl_bridge_main.py run-wrapper supervisor --dry-run
python3 openclaw/bridge/ainl_bridge_main.py drift-check --json
python3 openclaw/bridge/ainl_bridge_main.py memory-append "hello from cron"
```

Subcommands forward argv verbatim to the bridge implementation (`--dry-run`, `CRON_DRIFT_STRICT`, `AINL_DRY_RUN`, etc.).

**Token usage / budget (auto-discovered as `token-usage`):** prints and (unless `--dry-run`) appends a `## Token Usage Report` section to today’s OpenClaw daily memory. Reads `MONITOR_CACHE_JSON` plus recent daily markdown for token-like lines; compares to `AINL_ADVOCATE_DAILY_TOKEN_BUDGET` (default 500000). Warns when estimated usage ≥80% of budget.

```bash
python3 openclaw/bridge/ainl_bridge_main.py token-usage --dry-run
python3 openclaw/bridge/ainl_bridge_main.py token-usage --days-back 3
python3 openclaw/bridge/ainl_bridge_main.py token-usage --dry-run --json-output
```

Machine-readable JSON (`--json-output`) includes `total_tokens`, `budget_percent`, `budget_warning`, and `report_markdown` for wrappers.

## Scheduled reporting & alerting

**Wrapper:** `openclaw/bridge/wrappers/token_budget_alert.ainl` — scheduled daily (`S core cron "0 23 * * *"`). It uses **`R bridge monitor_cache_stat`** (size of `MONITOR_CACHE_JSON`; not `R fs stat`, which cannot reach `/tmp` from the sandbox), **`token_budget_warn` / `token_budget_report`**, **`token_budget_notify_*`**, then **`openclaw_memory.append_today`** into **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** (unless `--dry-run`).

**Live-only behaviors:**

- **Sentinel:** `token_report_today_sent` / `token_report_today_touch` prevent duplicating the **main** `## Token Usage Report` on repeated runs the same UTC day (`AINL_TOKEN_REPORT_SENTINEL` overrides default `/tmp/token_report_today_sent`). Dry-run skips sentinel and main append.
- **Consolidated notify:** A **single** `R queue Put` at the end (live) when any notify lines were queued; first line uses UTC from `R core now` (`Daily AINL Status - …`). May include critical cache, prune success, and/or budget text. Budget text is included only when **`budget_warning`** and cache **≤ 10 MB** (`cache_ok`).
- **Prune:** If cache **> 12 MB**, `monitor_cache_prune auto` runs after the report path; markdown success/error blocks append separately.

Full narrative + troubleshooting: `docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md` and `docs/operations/UNIFIED_MONITORING_GUIDE.md`.

**Run via bridge runner:**

```bash
python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run
```

**OpenClaw cron (example):**

```bash
openclaw cron add \
  --name ainl-token-budget-alert \
  --cron "0 23 * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert' \
  --description "AINL daily token usage, prune, consolidated notify"
```

Use `--dry-run` on the runner while validating; production jobs omit it so memory append runs.

## How to add a new bridge tool

1. Add the implementation under `openclaw/bridge/<tool>.py` with a `main()` guarded by `if __name__ == "__main__"` (same pattern as existing tools).
2. If old automation expected `scripts/<name>.py`, add a thin shim there that loads `_shim_delegate.py` and calls `run_bridge_script("<tool>.py")`.
3. Optionally register a subcommand in `openclaw/bridge/ainl_bridge_main.py`.
4. Document env vars, `--dry-run`, and cron examples in this README and, if user-facing, in `docs/ainl_openclaw_unified_integration.md`.

## Environment setup

Point shells, systemd units, and OpenClaw job env at your checkout (example path — use yours):

```bash
export AINL_WORKSPACE=/Users/clawdbot/.openclaw/workspace/AI_Native_Lang
# Add to ~/.bashrc, ~/.zshrc, systemd Environment=, or OpenClaw workspace env as needed
```

Cron payloads can then use `cd $AINL_WORKSPACE && python3 openclaw/bridge/...` so jobs stay portable.

### Shim checklist when adding bridge tools

After adding a new `openclaw/bridge/*.py` tool, run:

```bash
python3 openclaw/bridge/generate_shims.py --dry-run
```

It prints suggested `scripts/` shims (same pattern as existing delegators to `_shim_delegate.py`). By default it **only prints**; use **`--write`** (without `--dry-run`) to create missing shims after an interactive confirmation — see **Maintenance Checklist** below.

## Maintenance checklist

- After adding a new `*.py` tool under `openclaw/bridge/` → run `python3 openclaw/bridge/generate_shims.py --dry-run` to see required `scripts/` shims.
- To create **missing** shims only: `python3 openclaw/bridge/generate_shims.py --write` and answer `y` at the prompt (creates files; skipped if everything already exists).
- After a fresh clone, if `scripts/` shims are absent, run `generate_shims.py --write` once (confirm with `y`) to restore them — or copy from the printed templates.
- **`ainl_bridge_main.py`** subcommands for tools stay current via **auto-discovery**; you do not need to hand-maintain a list for new bridge `*.py` files (fixed aliases `run-wrapper`, `drift-check`, `memory-append` remain for compatibility).
