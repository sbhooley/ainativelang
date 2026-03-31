# OpenClaw + AINL — 5-minute quickstart

<!-- AINL-OPENCLAW-TOP5 -->

This path wires **gateway `env.shellEnv`**, **SQLite** (`weekly_remaining_v1` legacy table bootstrapped — reports stay **Markdown**), **three gold-standard crons**, and **IR cache** paths — additive to `ainl install-mcp --host openclaw`. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Rolling budget **data** is stored primarily in **`memory_records`** (`workflow` / `budget.aggregate` / `weekly_remaining_v1`); **`ainl status`** reads the legacy table when set, else falls back to that aggregate. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> For tuning (caps, schedules, verification cadence), use [`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md).

## Prerequisites

- Python **3.10+** and `ainl` on `PATH` (`pip install ainativelang`; current PyPI **v1.4.0**, or editable install).
- **OpenClaw CLI** on `PATH` (`openclaw --help` works).
- Optional: set `OPENCLAW_WORKSPACE` before commands so `ainl status` resolves the same workspace as your agents (otherwise default is `~/.openclaw/workspace` when that directory exists, else current working directory).

## One-command setup

Pick a workspace root (your OpenClaw workspace, often `~/.openclaw/workspace`):

```bash
ainl install openclaw --workspace ~/.openclaw/workspace
```

Preview changes without writing config, SQLite, crons, or restarting the gateway:

```bash
ainl install openclaw --workspace ~/.openclaw/workspace --dry-run
```

**What this does (non–dry-run):**

- Writes **`aiNativeLang.yml`** in the workspace if missing — copies from **`aiNativeLang.example.yml`** (repo root or `tooling/`) when present; otherwise safe defaults inline.
- Merges **`env.shellEnv`** keys directly into **`<workspace>/.openclaw/openclaw.json`** (OpenClaw CLI **`config set`** rejects AINL-specific keys — file merge is authoritative), including `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true`, `AINL_WEEKLY_TOKEN_BUDGET_CAP=100000`, `OPENCLAW_WORKSPACE`, `AINL_MEMORY_DB`, `MONITOR_CACHE_JSON`, `AINL_IR_CACHE_DIR`, and related paths.
- Idempotently creates **`weekly_remaining_v1`** under `AINL_MEMORY_DB` (`CREATE TABLE IF NOT EXISTS`). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> (Rolling budget **values** are published to **`memory_records`**; see gold standard §c.) <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
- Registers three crons if missing (same name or same payload message → skipped): **AINL Context Injection** (every 5 min), **AINL Session Summarizer**, **AINL Weekly Token Trends** — matching the gold-standard doc.
- Runs `openclaw gateway restart` (skipped when `--dry-run`).
- Prints a markdown health table (workspace, `aiNativeLang.yml`, env merge, schema, crons, drift, restart, IR cache).

### Example `ainl install openclaw` health report (realistic shape)

Markdown table (stdout):

```text
| | Check | Detail |
|---|---|---|
| 📁 | Workspace | /Users/you/.openclaw/workspace |
| ➖ | aiNativeLang.yml | already present |
| ✅ | env.shellEnv (+12 keys) | ok |
| ✅ | SQLite: weekly_remaining_v1 | ok (/path/.ainl/ainl_memory.sqlite3) (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->) |
| ✅ | Gold-standard crons (summary) | already registered (skipped): AINL Context Injection; … |
| ✅ | Cron: AINL Context Injection | registered |
| ✅ | Cron: AINL Session Summarizer | registered |
| ✅ | Cron: AINL Weekly Token Trends | registered |
| ✅ | 3 core cron jobs (gold-standard) | registered (or already present) |
| ✅ | Cron drift (read-only) | ok |
| ✅ | openclaw gateway restart | ok |
| ✅ | IR cache writable | /path/.cache/ainl/ir |
```

With `--dry-run`, **`env.shellEnv`** shows **preview on stderr**; SQL summary and three `openclaw cron add` argv lines print to **stderr** before the table.

## Check status

```bash
ainl status
```

Machine-readable JSON:

```bash
ainl status --json
```

**One-line outputs** (Telegram, Slack, CI): `ainl status --summary` (human-readable one line) or `ainl status --json-summary` (minified JSON one line). `--json`, `--json-summary`, and `--summary` are mutually exclusive; full **`--json`** includes a **`summary_line`** field.

**What `ainl status` shows:** workspace, schema bootstrap (including legacy **`weekly_remaining_v1`**), weekly budget row (or **Not initialized**), estimated **cost avoided (7d)** when token usage is available, the three core crons, drift signal via `cron_drift_check`, 7-day token totals via **`token_usage_reporter --json-output`**, caps from the current environment, and an overall health row. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> The **Weekly budget remaining** line uses **`_read_weekly_remaining_rollup`**: it prefers a non-null legacy table row, otherwise **`weekly_remaining_tokens`** from the latest **`memory_records`** aggregate — so you may see a number even when the legacy table has no row yet. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> If tables or crons are missing, the table points you at **`Run `ainl install openclaw` to initialize.`**

### Example `ainl status` table (realistic shape)

```text
| | Check | Detail |
|---|---|---|
| 📁 | Workspace | /Users/you/.openclaw/workspace |
| ✅ | SQLite schema | ok (/path/.ainl/ainl_memory.sqlite3) |
| ⚠️ | Weekly budget remaining | Not initialized — Run `ainl install openclaw` to initialize. |
| ✅ | Cron: AINL Context Injection | enabled=True last_run=— |
| ✅ | Cron: AINL Session Summarizer | enabled=True last_run=— |
| ✅ | Cron: AINL Weekly Token Trends | enabled=True last_run=— |
| ⚠️ | Token usage (7d) via token_usage_reporter --json-output | unknown — … |
| ⚠️ | Overall health | Needs attention — Run `ainl install openclaw` to initialize. … |
```

Use **`ainl status --json`** for the same fields as structured JSON (`fix_hint`, `weekly_budget_not_initialized`, `token_usage_error`, `cron_jobs`, `summary_line`, etc.).

## Schedule your own `.ainl` (optional)

```bash
ainl cron add path/to/workflow.ainl --cron "0 9 * * *"
# or
ainl cron add path/to/workflow.ainl --every 15m
```

Wraps **`openclaw cron add`** with message **`ainl run <quoted-path>`**. Use **`--dry-run`** to print argv only.

## Emitted dashboard (optional)

This UI is **not** part of a minimal **`pip install ainativelang`** tree: it lives under **`tests/emits/server/`** and is produced by the emitter test harness. Use a **git clone** of the repo, then build once:

```bash
python3 scripts/run_tests_and_emit.py
```

That creates **`tests/emits/server/server.py`**. **`ainl dashboard`** checks for that file first and prints the same hint if it is missing.

```bash
ainl dashboard
```

Runs **`scripts/serve_dashboard.py`**; **`--port`** and **`--no-browser`** supported.

## Project lock file

Canonical example: **`aiNativeLang.example.yml`** (and **`tooling/aiNativeLang.example.yml`** for wheels). **`ainl install openclaw`** copies to **`aiNativeLang.yml`** when missing.

## Validate with the doctor

```bash
ainl doctor --ainl
```

Runs the same OpenClaw integration validator as the bridge (`env`, schema bootstrap, cron names, `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT`) and prints fix hints plus **`openclaw_ainl_fix_suggestions`** (copy/paste commands, including `ainl install openclaw --workspace <absolute path>`).

## What just happened?

After `ainl install openclaw`, the gateway process should inherit **`env.shellEnv`** so bridge tools and intelligence programs see consistent paths. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Install bootstraps the legacy **`weekly_remaining_v1`** table; the bridge publishes rolling budget primarily to **`memory_records`**, which **`run_intelligence.py`** hydrates from — same logical key. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> Crons trigger **context**, **summarizer**, and **weekly token trends** on the schedule from the gold-standard doc. **`ainl status`** is the single place to see whether that wiring matches reality, including weekly budget via legacy row or **`memory_records`** fallback. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

## Common pitfalls

| Symptom | Likely cause | Fix |
|--------|----------------|-----|
| **`weekly_remaining_v1` missing — Run `ainl install openclaw` to initialize.** | DB never bootstrapped | Same command (idempotent `CREATE IF NOT EXISTS`) (`ainl status` now shows the value automatically via legacy-first + memory_records fallback <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->) |
| **Cron job 'AINL Weekly Token Trends' not found — Run `ainl install openclaw` to initialize.** | Crons not registered | `ainl install openclaw` (skips duplicate names/messages) |
| **`OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` should be true — … Run `ainl install openclaw` to initialize.** | Gateway env not patched or not restarted | Non–dry-run install or edit `env.shellEnv` + `openclaw gateway restart` |
| RPCWireError / connection refused | Gateway not running or unreachable | Start or `openclaw gateway restart`; confirm CLI can reach the host |
| **`ainl dashboard` / emitted server missing** | `tests/emits/server/server.py` not built (typical for PyPI-only installs) | From a git checkout: `python3 scripts/run_tests_and_emit.py` |
| **Workspace path mismatch — … Run `ainl install openclaw` to initialize.** | `OPENCLAW_WORKSPACE` / `AINL_MEMORY_DB` disagree | Align env; re-run install with `--workspace` |

## Next steps

- Deep reference: [`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md)
- Token observability: [`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](operations/TOKEN_AND_USAGE_OBSERVABILITY.md)
