# ZeroClaw integration

**Hub (all MCP hosts):** [`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host zeroclaw`** (same as **`ainl install-zeroclaw`**).

**PyPI:** `ainativelang` **v1.5.0**.

AINL ships a **ZeroClaw skill** (deterministic graphs, Markdown importer, **`ainl-mcp`**) and **`ainl install-mcp --host zeroclaw`** (alias **`ainl install-zeroclaw`**), a user-side bootstrap that wires PyPI, **`~/.zeroclaw/mcp.json`**, and **`~/.zeroclaw/bin/ainl-run`** without changing the ZeroClaw application itself.

**Memory:** ZeroClaw-hosted runs use the same AINL **`memory`** adapter and MCP tools as other hosts; they do **not** depend on OpenClaw’s **`~/.openclaw/workspace/memory/`** daily markdown (that path is **OpenClaw bridge**–specific). See [`docs/adapters/MEMORY_CONTRACT.md`](adapters/MEMORY_CONTRACT.md) and [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents).

**Why this matters:** AINL is **compile-once, run-many**—you pay authoring or import cost once, then execute a validated graph repeatedly. Size economics use **tiktoken cl100k_base**; on the **viable subset** of representative workloads, **minimal_emit** lands near **~1.02×** leverage vs unstructured baselines (see **[`BENCHMARK.md`](../BENCHMARK.md)** and **[`benchmarks.md`](benchmarks.md)** for methodology and legacy-inclusive transparency).

### Install AINL as a ZeroClaw skill

```bash
zeroclaw skills install https://github.com/sbhooley/ainativelang/tree/main/skills/ainl
```

This installs the AINL importer, runtime shim, and MCP tools directly into ZeroClaw.

[![ZeroClaw Skill](https://img.shields.io/badge/ZeroClaw%20Skill-AINL-blue)](https://github.com/sbhooley/ainativelang/tree/main/skills/ainl)

## Quickstart

1. **Install the skill** from the **main repo path** (above) or, when published separately, the standalone repo:

   ```bash
   zeroclaw skills install https://github.com/sbhooley/ainl-zeroclaw-skill
   cd <skill-checkout> && ./install.sh
   ```

   Or **from a local clone of this monorepo**:

   ```bash
   cd skills/ainl && ./install.sh
   ```

2. **Or run the bootstrap directly**:

   ```bash
   pip install 'ainativelang[mcp]'
   ainl install-mcp --host zeroclaw
   ```

   Preview: **`ainl install-mcp --host zeroclaw --dry-run`** (same flags as **`install-zeroclaw`**) · noisy logs: **`--verbose`**.

## Chat example

After a successful install, try:

> Import the morning briefing using AINL.

Then use **`ainl import markdown …`**, ecosystem shortcuts (**`ainl import clawflows`** / **`ainl import agency-agents`**), or MCP tools (**`ainl_list_ecosystem`**, **`ainl_import_clawflow`**, **`ainl_import_agency_agent`**, **`ainl_import_markdown`**) so the agent produces compiling **`.ainl`** source, followed by **`ainl compile`** / **`ainl run`** or **`~/.zeroclaw/bin/ainl-run my.ainl`**.

**Optional adapter — `code_context`:** graphs that call **`R code_context.*`** (tiered repo index, dependencies, impact, **`COMPRESS_CONTEXT`**) must pass **`--enable-adapter code_context`** to **`ainl run`** or **`~/.zeroclaw/bin/ainl-run`** (extra args forward to **`ainl run`**). Installing MCP does **not** enable optional adapters. Guide: **`docs/adapters/CODE_CONTEXT.md`** · demo **`examples/code_context_demo.ainl`** · optional env **`AINL_CODE_CONTEXT_STORE`**.

## What gets installed

| Artifact | Purpose |
|----------|---------|
| `pip install --upgrade 'ainativelang[mcp]'` | Latest compiler, importer extras, MCP dependencies |
| `~/.zeroclaw/mcp.json` | Merges an **`ainl`** stdio server entry pointing at **`ainl-mcp`** (skipped if already present with the same command) |
| `~/.zeroclaw/bin/ainl-run` | Shell wrapper: **`ainl compile "$1" && ainl run "$1"`** (plus extra args forwarded to **`ainl run`**) |
| `~/.bashrc` / `~/.zshrc` | Appends **`export PATH="$HOME/.zeroclaw/bin:$PATH"`** when those files exist and do not already mention **`~/.zeroclaw/bin`** |

If no shell rc file is updated, the command prints a one-line **`PATH`** tip you can paste manually.

When **`ainl install-mcp --host zeroclaw`** (or **`install-zeroclaw`**) is executed **from a repo checkout** that contains **`zeroclaw/bridge/`**, it also:

| Artifact | Purpose |
|----------|---------|
| **`~/.zeroclaw/config.toml`** **`[ainl_bridge]`** **`repo_root`** | Records the AINL git root for operators and shims |
| **`~/.zeroclaw/bin/zeroclaw-ainl-run`** | Runs **`zeroclaw/bridge/run_wrapper_ainl.py`** (wrapper registry with ZeroClaw memory paths) |

## Native bridge vs OpenClaw bridge

| Piece | OpenClaw (`openclaw/bridge/`) | ZeroClaw (`zeroclaw/bridge/`) |
|-------|-------------------------------|--------------------------------|
| Dispatcher CLI | `ainl_bridge_main.py` | `zeroclaw_bridge_main.py` |
| Wrapper runner | `run_wrapper_ainl.py` | `run_wrapper_ainl.py` (registers **`ZeroclawMemoryAdapter`** as **`openclaw_memory`** + **`zeroclaw_memory`**, **`ZeroclawQueueAdapter`**, **`ZeroclawBridgeTokenBudgetAdapter`**) |
| Daily markdown | `~/.openclaw/workspace/memory/` | `~/.zeroclaw/workspace/memory/` (overridable via **`ZEROCLAW_*`**) |
| Cron drift | `openclaw cron list --json` | `zeroclaw cron list --json` |
| Notify | `openclaw message send` | `zeroclaw message send` |
| Token-usage subprocess target | `openclaw/bridge/ainl_bridge_main.py` | `zeroclaw/bridge/zeroclaw_bridge_main.py` |

Detail: **`zeroclaw/bridge/README.md`**.

### Configuration namespaces (AINL vs ZeroClaw)

Bridge wrappers and token tooling reuse **`AINL_*`** names (**`AINL_DRY_RUN`**, **`AINL_BRIDGE_FAKE_CACHE_MB`**, **`AINL_TOKEN_PRUNE_DAYS`**, **`AINL_ADVOCATE_DAILY_TOKEN_BUDGET`**, etc.) so behavior matches the OpenClaw bridge and one document set covers both hosts.

ZeroClaw-specific wiring uses **`ZEROCLAW_*`**: workspace (**`ZEROCLAW_WORKSPACE`**), memory paths (**`ZEROCLAW_MEMORY_DIR`**), CLI path (**`ZEROCLAW_BIN`**), and notify routing (**`ZEROCLAW_NOTIFY_CHANNEL`**, **`ZEROCLAW_TARGET`**). **`ZEROCLAW_NOTIFY_TARGET`** controls **`zeroclaw message send`** for graphs that use **`R queue Put "notify" …`** (**`token-budget-alert`**, **`weekly-token-trends`**, **`monthly-token-summary`**). See **Configurable notifications** below and **`zeroclaw/bridge/README.md`**. If unset, the queue adapter uses **`ZEROCLAW_TARGET`** / **`OPENCLAW_TARGET`** and **`ZEROCLAW_NOTIFY_CHANNEL`** / **`OPENCLAW_NOTIFY_CHANNEL`**.

We are **not** introducing a separate `ZEROCLAW_AINL_*` prefix: shared bridge semantics stay **`AINL_*`**; host placement stays **`ZEROCLAW_*`**.

### Daily token budget alert

The **`token-budget-alert`** wrapper (**`zeroclaw/bridge/wrappers/token_budget_alert.ainl`**) is the daily cache/token digest; run **`zeroclaw-ainl-run token-budget-alert`** (or **`python3 zeroclaw/bridge/run_wrapper_ainl.py token-budget-alert`**). Env vars and smoke patterns: **`zeroclaw/bridge/README.md`**.

Daily, weekly, and monthly token summaries are **timezone-agnostic** (UTC-based date tags and **`YYYY-MM-DD.md`** filenames); adjust the declared cron hour on your host to a **local** time that is easy to read in your logs.

### Weekly token trends

The **`weekly-token-trends`** wrapper (**`zeroclaw/bridge/wrappers/weekly_token_trends.ainl`**) complements the daily token digest. It does **not** add background scheduling inside the AINL runtime—the graph only declares a suggested cron line; your host or ZeroClaw job runner must invoke **`zeroclaw-ainl-run weekly-token-trends`** (or **`python3 zeroclaw/bridge/run_wrapper_ainl.py weekly-token-trends`**) on that schedule.

Suggested cron: **`0 9 * * 0`** (Sunday 09:00 UTC). Adjust to your timezone and load; weekly runs are low-impact compared to the daily token digest. Same **timezone-agnostic** note as the daily wrapper (UTC-based parsing; pick a **local** cron hour for readability).

| Aspect | Behavior |
|--------|----------|
| **Inputs** | Newest 14 files matching **`YYYY-MM-DD.md`** under **`ZEROCLAW_WORKSPACE/memory/`** (or **`ZEROCLAW_MEMORY_DIR`**), same layout as daily bridge notes. Each file may contain a **`## Token Usage Report`** section (heuristic parse: `estimated_total_tokens`, `budget_used_pct`, etc.). |
| **Processing** | **`ZeroclawBridgeTokenBudgetAdapter`** (**`R bridge weekly_token_trends_report`**) aggregates the last 7 days (or fewer if not enough files), compares halves for a short trend arrow, and optionally compares to the prior 7 days when 14 files exist. |
| **Outputs** | Markdown starting with **`## Weekly Token Trends`**. If **`--dry-run`**: report is returned in JSON **`out`** only; **`R openclaw_memory append_today`** and **`R queue Put "notify" …`** are skipped. If live: append via **`R openclaw_memory append_today`**, then a short **`R queue Put "notify" …`** (routing: **`ZEROCLAW_NOTIFY_TARGET`** / **`ZeroclawQueueAdapter`**). |
| **Sentinel / de-dupe** | Unlike **`token-budget-alert`**, this graph has **no** token-report date sentinel (no **`AINL_TOKEN_REPORT_SENTINEL`**-style guard). Avoid double appends by not running the job twice on the same calendar day, or by scheduling only from cron. |

### Monthly token summary

The **`monthly-token-summary`** wrapper (**`zeroclaw/bridge/wrappers/monthly_token_summary.ainl`**) aggregates roughly a **month** of usage from daily notes. Like weekly, it does **not** start background jobs inside AINL—only a suggested cron line in the source; invoke **`zeroclaw-ainl-run monthly-token-summary`** (or **`python3 zeroclaw/bridge/run_wrapper_ainl.py monthly-token-summary`**) from your scheduler.

Suggested cron: **`0 3 1 * *`** (1st of month, 03:00 UTC). Tune for **timezone and load**; same **timezone-agnostic** convention as daily/weekly (UTC window from **`YYYY-MM-DD.md`** stems; use a **local** cron hour if you prefer wall-clock alignment).

| Aspect | Behavior |
|--------|----------|
| **Inputs** | Daily **`YYYY-MM-DD.md`** under **`ZEROCLAW_WORKSPACE/memory/`** (or **`ZEROCLAW_MEMORY_DIR`**) whose stem date falls in the **rolling last 30 calendar days (UTC)**. Same **`## Token Usage Report`** heuristics as weekly. |
| **Processing** | **`ZeroclawBridgeTokenBudgetAdapter`** (**`R bridge monthly_token_summary_report`**) sums token estimates in that window, **Avg daily**, **Trend** (split-window), and **vs prior 30 days** when the prior period has data. |
| **Outputs** | Markdown starting with **`## Monthly Token Summary`**. Report includes an optional **vs prior 30 days** line when enough older daily notes exist. **`--dry-run`**: JSON **`out`** only; no **`append_today`**, no queue notify. Live: append via **`R openclaw_memory append_today`**, then short **`R queue Put "notify" …`** (same routing as daily/weekly). |
| **Sentinel / de-dupe** | **No** monthly sentinel—rely on running **once per month** from cron or manual discipline. |

All three monitoring wrappers append reports to today's daily note on live runs and trigger a short notification via the queue (routed by **`ZEROCLAW_NOTIFY_TARGET`**). Use **`--dry-run`** for testing without side effects. Live runs can also emit JSON output with **`--json`**, **`--output=json`**, and **`--pretty`** (see **`zeroclaw/bridge/run_wrapper_ainl.py`**).

<a id="cadence-overview"></a>

### Monitoring Cadence Overview

| Wrapper               | Cadence | Purpose                            | Suggested Cron (UTC) | Output Location    | Notification Routing                         | JSON output support                                      |
|-----------------------|---------|------------------------------------|----------------------|--------------------|----------------------------------------------|----------------------------------------------------------|
| **`token-budget-alert`**   | Daily   | Budget check + prune + alert     | `0 23 * * *`         | Today's daily note | Yes (via **`ZEROCLAW_NOTIFY_TARGET`**)       | Yes (`--json`, `--output=json`, `--pretty`)              |
| **`weekly-token-trends`**  | Weekly  | 7-day trends & stats               | `0 9 * * 0`          | Today's daily note | Yes (via **`ZEROCLAW_NOTIFY_TARGET`**)       | Yes (`--json`, `--output=json`, `--pretty`)              |
| **`monthly-token-summary`** | Monthly | 30-day overview + prior comparison | `0 3 1 * *`        | Today's daily note | Yes (via **`ZEROCLAW_NOTIFY_TARGET`**)       | Yes (`--json`, `--output=json`, `--pretty`)              |

*Extending the table:* When you add a production monitoring wrapper, register its CLI name in **`zeroclaw/bridge/run_wrapper_ainl.py`**, keep cadence/cron hints in the **`.ainl`** header, document behavior under a new `###` subsection above, and append a row here (same columns: cadence, purpose, cron, note append + queue notify, **`ZEROCLAW_NOTIFY_TARGET`**, JSON flags if supported). If a new wrapper omits notifications or JSON output, update the corresponding cell (e.g. **No** or **Dry-run only**).

### Configurable notifications

All three wrappers now send a short notification via the queue on live runs (routed by **`ZEROCLAW_NOTIFY_TARGET`**). The full report is always appended to today's daily note.

Each **live** run ends with **`R queue Put "notify" …`** (payload: full daily digest text vs short weekly/monthly summary lines). **`ZeroclawQueueAdapter`** maps every such put to **`zeroclaw message send`** using **`ZEROCLAW_NOTIFY_TARGET`** and related env vars. **`--dry-run`** skips **`append_today`** and the queue put for all three.

Set **`ZEROCLAW_NOTIFY_TARGET`** in the shell or cron (case-insensitive where noted):

| Value | Behavior |
|-------|----------|
| *(unset or empty)* | **`--target`**: **`ZEROCLAW_TARGET`** then **`OPENCLAW_TARGET`**; **`--channel`**: **`ZEROCLAW_NOTIFY_CHANNEL`** / **`OPENCLAW_NOTIFY_CHANNEL`** (default **`telegram`**) |
| **`none`** | Skip **`zeroclaw message send`** entirely (live runs only; **`--dry-run`** still skips as before) |
| **`slack:`**_rest_ | **`--channel slack`**, **`--target`** = _rest_ (after first **`:`**) |
| **`email:`**_rest_ | **`--channel email`**, **`--target`** = _rest_ |
| **`telegram:`**_rest_ | **`--channel telegram`**, **`--target`** = _rest_ (numeric chat id, **`@username`**, etc.) |
| Plain string (no recognized prefix) | **`--target`** = full string, **`--channel`** from env (legacy override) |

Examples:

```bash
ZEROCLAW_NOTIFY_TARGET=slack:zero-claw-alerts zeroclaw-ainl-run token-budget-alert
ZEROCLAW_NOTIFY_TARGET=telegram:-1001234567890 zeroclaw-ainl-run weekly-token-trends
ZEROCLAW_NOTIFY_TARGET=none zeroclaw-ainl-run monthly-token-summary
```

The message body is the same payload that would have been sent to the default queue path. Actual delivery depends on your **`zeroclaw`** CLI supporting each **`--channel`**.

### Why CLI calls?

ZeroClaw’s Rust traits and on-disk layout are **extensible** and may shift between releases. For the native bridge we call **`zeroclaw` CLI subcommands** (cron list, message send, memory search where available) instead of parsing or writing TOML/DB internals from Python: **CLI is the simplest stable surface and stays version-agnostic for now**. Where no CLI exists (e.g. appending daily markdown), we write the same **`YYYY-MM-DD.md`** files under **`~/.zeroclaw/workspace/memory/`** as a deliberate, documented contract.

## Ecosystem transparency (honest story)

- **Importer:** CLI **`ainl import markdown`**, **`ainl import clawflows`**, **`ainl import agency-agents`** share the same Markdown → graph path as the MCP tools above. When structure cannot be parsed, a **minimal_emit fallback stub** still yields compiling **`.ainl`** for review.
- **Checked-in samples:** **[`examples/ecosystem/`](../examples/ecosystem/)** holds **`original.md`**, **`converted.ainl`**, and per-folder READMEs; **weekly auto-sync** ( **[`.github/workflows/sync-ecosystem.yml`](../.github/workflows/sync-ecosystem.yml)** ) keeps them aligned with upstream public Markdown—see **[`ECOSYSTEM_OPENCLAW.md`](ECOSYSTEM_OPENCLAW.md)**.
- **Contributions:** submit new workflows or agents via **[`.github/PULL_REQUEST_TEMPLATE/`](../.github/PULL_REQUEST_TEMPLATE/)** (Clawflows-style workflow or Agency-Agents-style agent templates).

## Benefits (summary)

| Benefit | Notes |
|---------|--------|
| Deterministic graphs | Compile-time validation; explicit cron, steps, and branches vs prose-only prompts |
| One-command skill path | **ZeroClaw skill** + **`install.sh`** or **`ainl install-mcp --host zeroclaw`** |
| MCP parity | Same import semantics as CLI; exposure profiles in **`tooling/mcp_exposure_profiles.json`** |
| Fresh ecosystem examples | Auto-sync + PR templates for community extensions |

## See also

- **All MCP hosts:** **[`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)**
- **OpenClaw parallel (skill + `ainl install-mcp --host openclaw`):** **[`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)** · **[`skills/openclaw/README.md`](../skills/openclaw/README.md)**
- **Monitoring (OpenClaw vs ZeroClaw runners):** **[`docs/operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md)** · **`zeroclaw/bridge/README.md`**
- Skill manifest & usage: **[`skills/ainl/README.md`](../skills/ainl/README.md)**
- MCP operator guide: **[`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](operations/EXTERNAL_ORCHESTRATION_GUIDE.md)** §9 (stdio **`ainl-mcp`**)
- Integration narrative: **[`docs/INTEGRATION_STORY.md`](INTEGRATION_STORY.md)**
- Ecosystem sync & OpenClaw- / ZeroClaw-oriented examples: **[`docs/ECOSYSTEM_OPENCLAW.md`](ECOSYSTEM_OPENCLAW.md)**
- Compile-once framing: **[`docs/architecture/COMPILE_ONCE_RUN_MANY.md`](architecture/COMPILE_ONCE_RUN_MANY.md)**

## LLM Adapter Setup

To enable cloud LLM providers, create an AINL config file following the guide in `docs/LLM_ADAPTER_USAGE.md`. Set your provider API keys via environment variables (e.g., `OPENROUTER_API_KEY`). Then pass the config path using `--config` or set `AINL_CONFIG`.

You can verify cost tracking and retry behavior by running a program and checking the SQLite DB under `intelligence/monitor/`.

