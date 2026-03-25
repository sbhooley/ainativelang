# OpenClaw host briefing — AINL **v1.2.8** (install / update)

**Audience:** You are the **OpenClaw host** — the process that owns config, cron, workspace paths, and **what gets injected into the agent** at session start.

**Companion docs:** [`OPENCLAW_AINL_GOLD_STANDARD.md`](OPENCLAW_AINL_GOLD_STANDARD.md) (schedules + checklist) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) · [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`../INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md) · [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)

---

## What the AINL **v1.2.8** repo includes (you consume; you don’t reimplement)

| Capability | What it is |
|------------|------------|
| **Evidence + sizing** | `ainl bridge-sizing-probe` (and `scripts/bridge_sizing_probe.py`) samples SQLite namespace counts and sizes of `## Token Usage Report` sections in daily memory, and suggests an **`AINL_BRIDGE_REPORT_MAX_CHARS`** target. CI exercises the probe. |
| **Rolling budget → intelligence cache** | After the bridge publishes **`workflow` / `budget.aggregate` / `weekly_remaining_v1`**, `scripts/run_intelligence.py` merges that into **`MONITOR_CACHE_JSON`** under **`workflow` → `token_budget`** before each run (unless **`AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE=1`**). JSON output includes **`budget_hydrate`**. This matches a **single aggregate read** instead of scanning many days of markdown. |
| **Caps documentation** | [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) and [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md): staging order — bridge (`AINL_BRIDGE_REPORT_MAX_CHARS`), then gateway (`PROMOTER_LLM_*`), with **measurement first**. |
| **Named env profiles** | `tooling/ainl_profiles.json` + `ainl profile list | show | emit-shell` — **`dev`**, **`staging`**, **`openclaw-default`**, **`cost-tight`** so installs share a baseline without one-off env drift. |
| **Operator docs** | Embedding pilot, WASM notes, TTL tuner, workspace isolation, [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md), and [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) (agent vs AINL roles; **curated bootstrap must be loaded**). |
| **Intelligence programs** | In-tree: [`intelligence/token_aware_startup_context.lang`](../../intelligence/token_aware_startup_context.lang) writes **`.openclaw/bootstrap/session_context.md`**; [`intelligence/proactive_session_summarizer.lang`](../../intelligence/proactive_session_summarizer.lang) summarizes prior days. Run via **`python3 scripts/run_intelligence.py context`** \| **`summarizer`** \| … |

Upgrade path: **`pip install -U 'ainl-lang[mcp]'`** (or editable install from this repo), then **`ainl install-mcp --host openclaw`** if you use MCP. See [`../INSTALL.md`](../INSTALL.md) for **`RUNTIME_VERSION`** / **`__pycache__`** after upgrades.

---

## What the OpenClaw host **must** do (explicit)

### 1. Host contract — non-negotiable for chat-layer savings

When startup context has run, **prefer injecting** **`session_context.md`** (or the same curated path your layout uses) into the agent session **instead of** always loading the full **`MEMORY.md`** for bootstrap.

If the host ignores the curated file, **token savings from AINL never appear in the chat layer** — you only update files and subprocesses the model never sees.

See [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md). Prefer an **upstream-supported** bootstrap order; patching **`node_modules`** is fragile across OpenClaw upgrades.

### 2. Scheduling

- **Cron / jobs** that actually run:
  - **`python3 scripts/run_intelligence.py context`** (and **`summarizer`** on your chosen cadence — see [gold standard](OPENCLAW_AINL_GOLD_STANDARD.md) for suggested times).
  - Bridge: at minimum **weekly token trends** (or equivalent) so **`rolling_budget_publish`** can write **`weekly_remaining_v1`** to SQLite.
- Use the **same** **`OPENCLAW_WORKSPACE`**, **`OPENCLAW_MEMORY_DIR`**, **`AINL_MEMORY_DB`**, **`MONITOR_CACHE_JSON`** (and siblings from [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md)) as **`run_wrapper_ainl.py`** and intelligence — one workspace, one truth.

### 3. Environment

- Operators can **`eval "$(ainl profile emit-shell openclaw-default)"`** (or **`cost-tight`** after measuring) for baseline **`AINL_*`** flags.
- Set **`AINL_WEEKLY_TOKEN_BUDGET_CAP`** if you want **`weekly_remaining_tokens`** in rolling JSON to match your real budget.
- **Gateway-only:** set **`PROMOTER_LLM_MAX_PROMPT_CHARS`** / **`PROMOTER_LLM_MAX_COMPLETION_TOKENS`** on the Apollo / gateway process per **`TOKEN_CAPS_STAGING.md`** (staging order — measure first).

### 4. Verification

- After a **weekly** bridge run: confirm **`weekly_remaining_v1`** exists in SQLite and that **`run_intelligence.py`** prints **`budget_hydrate`** with **`ok: true`** (not permanently **`skipped`** / **`no_rolling_record`** only).
- Use **`ainl bridge-sizing-probe --json`** **before** tightening **`AINL_BRIDGE_REPORT_MAX_CHARS`**.

---

## Bottom line

The AINL **v1.2.8** tree delivers **measurement**, **rolling-budget → cache hydration**, **profiles**, **caps staging docs**, and **clear host responsibilities**.

The remaining gap for **~85–90%** usage/cost savings on **session bootstrap** is **host behavior**: **load curated context** + **run scheduled intelligence + bridge jobs on shared paths**. Without that, savings stay in files and subprocesses the **model never reads**.

Optional next tier (pilots, one at a time): [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md), [`WASM_OPERATOR_NOTES.md`](WASM_OPERATOR_NOTES.md), [`TTL_MEMORY_TUNER.md`](TTL_MEMORY_TUNER.md).

---

## Agent discovery

- **`tooling/bot_bootstrap.json`** → **`openclaw_ainl_gold_standard`** (checklist) · **`openclaw_host_ainl_1_2_8`** (this briefing)
