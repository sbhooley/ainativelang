# ZeroClaw bridge (`zeroclaw/bridge/`)

Parallel to **`openclaw/bridge/`**, this directory holds **ZeroClaw-specific** helpers: wrapper runner, cron drift check, daily memory append, token budget adapter, and a dispatcher CLI. They are **not** part of AINL canonical core.

## Differences vs OpenClaw bridge

| Topic | OpenClaw | ZeroClaw |
|--------|-----------|----------|
| Dispatcher | `openclaw/bridge/ainl_bridge_main.py` | `zeroclaw/bridge/zeroclaw_bridge_main.py` |
| Daily memory dir | `OPENCLAW_WORKSPACE/memory/` (or `OPENCLAW_MEMORY_DIR`) | `ZEROCLAW_WORKSPACE/memory/` (default `~/.zeroclaw/workspace/memory/`) |
| Memory adapter | `OpenClawMemoryAdapter` (`adapters/openclaw_memory.py`) | `ZeroclawMemoryAdapter` (this dir) — also registered as **`openclaw_memory`** so shared `.ainl` wrappers append under ZeroClaw paths |
| Notify queue | `openclaw message send` | `zeroclaw message send` (`ZeroclawQueueAdapter`; see env table: channel + target) |
| Cron drift | `openclaw cron list --json` | `zeroclaw cron list --json` (`cron_drift_check.py`) |
| Token subprocess | `ainl_bridge_main.py token-usage` | `zeroclaw_bridge_main.py token-usage` |
| FS sandbox default | `AINL_FS_ROOT` / `~/.openclaw/workspace` | `ZEROCLAW_WORKSPACE` / `~/.zeroclaw/workspace` |

## Install wiring (`ainl install-zeroclaw`)

When run from a git checkout that contains `zeroclaw/bridge/zeroclaw_bridge_main.py`, the installer also:

1. Appends **`[ainl_bridge]`** with **`repo_root`** to **`~/.zeroclaw/config.toml`** (skipped if `[ainl_bridge]` already exists).
2. Installs **`~/.zeroclaw/bin/zeroclaw-ainl-run`**, a shim that `cd`s to `repo_root` and runs **`python3 zeroclaw/bridge/run_wrapper_ainl.py`**.

`~/.zeroclaw/bin/ainl-run` (compile+run `.ainl`) is unchanged.

## Production wrappers (`wrappers/`)

ZeroClaw copies of bridge orchestration graphs live under **`zeroclaw/bridge/wrappers/`** (parallel to `openclaw/bridge/wrappers/`). They use the same `R openclaw_memory` / `R bridge` / `R queue` spellings; the ZeroClaw runner registers **`openclaw_memory`** to **`ZeroclawMemoryAdapter`**, so daily notes and FS sandbox resolve under **`ZEROCLAW_WORKSPACE`** (default **`~/.zeroclaw/workspace`**).

| Wrapper (`.ainl`) | CLI name | Notes |
|-------------------|----------|--------|
| `token_budget_alert.ainl` | `token-budget-alert` | Daily token/cache digest, prune, notify via `zeroclaw message send` |
| `weekly_token_trends.ainl` | `weekly-token-trends` | Sunday cron hint: aggregate last 7–14 daily `memory/*.md` → `## Weekly Token Trends`; live: append + short `R queue Put "notify"` (`ZEROCLAW_NOTIFY_TARGET`) |
| `monthly_token_summary.ainl` | `monthly-token-summary` | Rolling 30-day UTC summary → `## Monthly Token Summary`; live: append + short queue notify (same routing as daily/weekly) |

All wrappers share the same runner (`zeroclaw-ainl-run` / `run_wrapper_ainl.py`) and memory bridge — change only the wrapper name on the command line.

### Wrapper runner JSON stdout (`run_wrapper_ainl.py`)

- **`--dry-run`**, **`--json`**, or **`--output=json`**: print one JSON object: **`status`** (`"ok"`), **`out`** (markdown string or empty), **`wrapper`** (CLI name).
- **`--pretty`**: indent JSON; default is compact one line.
- **Live** without those flags: **no stdout** (append + queue notify still run). See **`docs/ZEROCLAW_INTEGRATION.md`** for the monitoring cadence table. For per-file **`## Token Usage Report`** parsing from graphs, **`include "modules/common/token_report_parser.ainl"`** (uses **`R bridge token_report_parse_block`** / **`token_report_list_daily_md`**). Future wrappers can replace direct **`R bridge`** calls with **`Call tr/PARSE_DAILY_TOKEN_REPORT`** or **`Call tr/EXTRACT_TOKEN_STATS`** for cleaner graphs.

Run after `ainl install-zeroclaw` (or from a checkout):

```bash
zeroclaw-ainl-run token-budget-alert --dry-run
zeroclaw-ainl-run weekly-token-trends --dry-run
zeroclaw-ainl-run monthly-token-summary --dry-run
```

### Examples with custom notification routing

**`token-budget-alert`**, **`weekly-token-trends`**, and **`monthly-token-summary`** each call **`R queue Put "notify" …`** on **live** runs; **`ZeroclawQueueAdapter`** maps that to **`zeroclaw message send`**. Weekly/monthly use a short “see today’s daily note” message; the full report is still in the note. **`--dry-run`** skips the queue for all three.

```bash
# Daily alert → Slack channel (requires `zeroclaw message send --channel slack` support)
ZEROCLAW_NOTIFY_TARGET=slack:zero-claw-alerts \
  zeroclaw-ainl-run token-budget-alert

# Weekly → Telegram (live only; --dry-run skips send)
ZEROCLAW_NOTIFY_TARGET=telegram:@zero_claw_group \
  zeroclaw-ainl-run weekly-token-trends --dry-run

# Monthly → email
ZEROCLAW_NOTIFY_TARGET=email:team@example.com \
  zeroclaw-ainl-run monthly-token-summary

# Staging: skip live send entirely
ZEROCLAW_NOTIFY_TARGET=none zeroclaw-ainl-run token-budget-alert
```

See **`docs/ZEROCLAW_INTEGRATION.md`** (**Configurable notifications**) for prefix rules and fallbacks.

**Smoke test (fake cache size, dry-run):** the bridge honors `AINL_BRIDGE_FAKE_CACHE_MB` so you can exercise the over-12MB prune branch without a real cache file. No `zeroclaw message send` occurs when `--dry-run` is set.

```bash
# Expect: fake cache size crosses 12MB threshold → prune + alert branches run (still no live send)
AINL_BRIDGE_FAKE_CACHE_MB=15.7 \
  zeroclaw-ainl-run token-budget-alert --dry-run
```

Same from a repo checkout:

```bash
AINL_BRIDGE_FAKE_CACHE_MB=15.7 \
  python3 zeroclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run
```

Automated compile smoke: `pytest tests/test_zeroclaw_wrappers.py`.

## Usage

```bash
cd /path/to/AI_Native_Lang
python3 zeroclaw/bridge/zeroclaw_bridge_main.py run-wrapper supervisor --dry-run
python3 zeroclaw/bridge/zeroclaw_bridge_main.py token-usage --dry-run --json-output
python3 zeroclaw/bridge/zeroclaw_bridge_main.py drift-check --json
```

Or after install:

```bash
zeroclaw-ainl-run token-budget-alert --dry-run
```

## Execution model

`run_wrapper_ainl.py` embeds **`RuntimeEngine`** with a ZeroClaw-tuned registry (same pattern as OpenClaw). Bare **`ainl run`** does not load this registry; use this script or **`zeroclaw-ainl-run`**.

Optional: **`AINL_ZC_COMPILE_SUBPROCESS=1`** runs **`ainl compile &lt;wrapper&gt;`** in a subprocess before in-process execution (toolchain check). Pass **`--verbose`** / **`-v`** to **`run_wrapper_ainl.py`** to set **`AINL_ZC_WRAPPER_VERBOSE`** and emit extra bridge logs (e.g. which daily **`*.md`** files weekly / monthly aggregations scanned).

## Environment variables

**Namespace:** **`ZEROCLAW_*`** (and `ZEROCLAW_NOTIFY_*`) select the ZeroClaw install, workspace, and notify routing. **`AINL_*`** stays the shared bridge / token-budget surface (same names as OpenClaw) so one mental model works across hosts. **`OPENCLAW_*`** is only a fallback for notify target/channel when ZeroClaw vars are unset.

| Variable | Role |
|----------|------|
| `ZEROCLAW_WORKSPACE` | Base for `memory/` and default FS sandbox |
| `ZEROCLAW_MEMORY_DIR` / `ZEROCLAW_DAILY_MEMORY_DIR` | Override daily markdown directory |
| `ZEROCLAW_BIN` | `zeroclaw` CLI path |
| `ZEROCLAW_NOTIFY_CHANNEL` | `zeroclaw message send --channel` (fallback: `OPENCLAW_NOTIFY_CHANNEL`, default `telegram`) |
| `ZEROCLAW_NOTIFY_TARGET` | Routing for `zeroclaw message send`: `slack:…` / `email:…` / `telegram:…` set `--channel` + `--target`; plain string → `--target` with default channel; `none` → skip send; unset → `ZEROCLAW_TARGET` / `OPENCLAW_TARGET` |
| `ZEROCLAW_TARGET` | Notify recipient if `ZEROCLAW_NOTIFY_TARGET` is unset (fallback: `OPENCLAW_TARGET`) |
| `MONITOR_CACHE_JSON`, `AINL_DRY_RUN`, `AINL_ADVOCATE_DAILY_TOKEN_BUDGET`, `AINL_BRIDGE_FAKE_CACHE_MB`, `AINL_TOKEN_*` | Shared AINL bridge / token semantics (same as OpenClaw) |
| `AINL_REPO_ROOT` | Set by `zeroclaw-ainl-run` shim |
| `AINL_ZC_COMPILE_SUBPROCESS` | When `1`/`true`, run `ainl compile` on the wrapper before execute |
| `AINL_ZC_WRAPPER_VERBOSE` | Set to `1` by **`--verbose`** / **`-v`** on **`run_wrapper_ainl.py`**; enables INFO logs such as weekly trends file parsing (can also export manually) |

## See also

- `docs/ZEROCLAW_INTEGRATION.md` — skill + MCP + bridge overview  
- `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` — orchestration + bridge pointers  
- `openclaw/bridge/README.md` — OpenClaw reference  
