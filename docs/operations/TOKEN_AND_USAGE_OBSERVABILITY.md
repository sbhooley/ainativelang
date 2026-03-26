# Token and usage observability (evidence-based savings)

This page is a **single map** for humans and coding agents: where to **read** token-related signals, **what** each surface means, and **which env vars** tune caps. Use it to validate claims like “~90% savings” against **real traces**, not aspirational totals.

## Layers (orthogonal)

| Layer | What gets measured | Typical signals |
|-------|--------------------|-----------------|
| **Apollo / gateway LLM** | Chat completions used by promoter-style HTTP routes | `llm.usage` audit rows (`prompt_tokens`, `completion_tokens`, `usage_context`) when the gateway records usage |
| **OpenClaw daily markdown** | Human-facing digest lines in `YYYY-MM-DD.md` | `## Token Usage Report` blocks (heuristic totals from bridge tooling) |
| **SQLite `memory` adapter** | Workflow / session rows (source of truth for structured state) | `memory.get` / `memory.list`; rolling aggregate key (below) |
| **Bridge subprocess** | `ainl_bridge_main.py token-usage --json-output` | Feeds `BridgeTokenBudgetAdapter` reports and dashboards |
| **AINL CLI trajectory** | Per-step JSONL beside a source file | `ainl run --log-trajectory` / `AINL_LOG_TRAJECTORY` → `*.trajectory.jsonl` (not the HTTP runner audit stream; see `docs/operations/AUDIT_LOGGING.md`) |

## High-signal locations (defaults)

| Artifact | Default path | Override |
|----------|--------------|----------|
| Daily OpenClaw markdown | `~/.openclaw/workspace/memory/YYYY-MM-DD.md` | `OPENCLAW_MEMORY_DIR`, `OPENCLAW_DAILY_MEMORY_DIR`, `OPENCLAW_WORKSPACE` |
| Monitor cache JSON | `/tmp/monitor_state.json` | `MONITOR_CACHE_JSON` |
| SQLite workflow memory | `/tmp/ainl_memory.sqlite3` (many scripts) | `AINL_MEMORY_DB` |
| Embedding sidecar index | `/tmp/ainl_embedding_memory.sqlite3` | `AINL_EMBEDDING_MEMORY_DB` |
| IR compile cache (wrappers) | `~/.cache/ainl/ir` | `AINL_IR_CACHE_DIR`; disable with `AINL_IR_CACHE=0` |

## Rolling budget aggregate (cheap read for monitors)

After **`weekly-token-trends`** runs (live), the bridge may write:

- **namespace** `workflow`
- **record_kind** `budget.aggregate`
- **record_id** `weekly_remaining_v1`

**Read:** `memory.get` on that key, or **`R bridge rolling_budget_json`** (JSON string). Prefer this over re-scanning many days of markdown when you only need a single number.

### Intelligence runner + cache (`scripts/run_intelligence.py`)

Before each non–dry-run execution, the runner calls **`tooling/intelligence_budget_hydrate.hydrate_budget_cache_from_rolling_memory`**: it reads **`workflow` / `budget.aggregate` / `weekly_remaining_v1`** from SQLite (when present) and **merges** rolling fields into **`MONITOR_CACHE_JSON`** under **`workflow` → `token_budget`**, which `token_aware_startup_context` and `proactive_session_summarizer` already read via **`R cache get "workflow" "token_budget"`**.

- Disable with **`AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE=1`**.  
- Merge policy for **`daily_remaining`**: see **`docs/operations/TOKEN_CAPS_STAGING.md`**.

The JSON result includes a **`budget_hydrate`** field for observability.

## Gateway / promoter caps (Apollo)

Set on the process that runs `apollo-x-bot/gateway_server.py`:

| Variable | Role |
|----------|------|
| `PROMOTER_LLM_MAX_PROMPT_CHARS` | Truncate chat `messages` to the last N characters |
| `PROMOTER_LLM_MAX_COMPLETION_TOKENS` | Pass `max_tokens` to the chat completions API |
| `PROMOTER_LLM_EXTRA_BODY_JSON` / `OPENAI_CHAT_EXTRA_BODY_JSON` | Merge JSON into the request body (provider-specific) |

## Bridge report cap (token-budget markdown)

| Variable | Role |
|----------|------|
| `AINL_BRIDGE_REPORT_MAX_CHARS` | If set (>0), caps **`token_budget_report`** markdown length; overflow returns a short **budget exhausted** stub instead of a huge report |

## Wrapper-level low-budget guard (bridge runner)

The OpenClaw wrapper runner (`python3 openclaw/bridge/run_wrapper_ainl.py <name>`) can skip **noncritical** wrappers when rolling budgets are low (read from `MONITOR_CACHE_JSON.workflow.token_budget`).

| Variable | Role |
|----------|------|
| `AINL_WRAPPER_MIN_DAILY_REMAINING` | Skip noncritical wrappers when `daily_remaining` falls below this (default `1000`) |
| `AINL_WRAPPER_MIN_WEEKLY_REMAINING` | Skip noncritical wrappers when `weekly_remaining_tokens` falls below this (default `5000`) |
| `AINL_WRAPPER_BUDGET_GUARDS_JSON` | Per-wrapper overrides / forced skips (JSON). Example: `{"weekly-token-trends":{"min_weekly":10000},"ttl-memory-tuner":{"skip":true}}` |

## Embedding pilot (index + search)

| Variable | Role |
|----------|------|
| `AINL_EMBEDDING_INDEX_NAMESPACE` | Namespace to scan for indexing (default `workflow`) |
| `AINL_EMBEDDING_MODE` | `stub` (default) or `openai` for real embeddings (`adapters/embedding_memory.py`) |

| `AINL_STARTUP_USE_EMBEDDINGS` | Enables an optional embedding top-k candidate path inside `token_aware_startup_context`; safe fallback always exists |

Activation detail:

- `token_aware_startup_context` uses embedding hits only when `AINL_EMBEDDING_MODE != stub` (so profiles can keep `AINL_STARTUP_USE_EMBEDDINGS=1` without breaking embeddings).
- `proactive_session_summarizer` stores the actual terse bullet text into `payload.summary` for `workflow.session_summary` records, so `embedding_workflow_index/search` returns meaningful snippets for startup.

Wrapper: **`python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot --dry-run`**

Bridge verbs: **`embedding_workflow_index`**, **`embedding_workflow_search`** (see `openclaw/bridge/bridge_token_budget_adapter.py`).

## How an agent should validate savings

1. Identify **which layer** dominates spend (gateway vs OpenClaw md vs monitors).
2. Before/after: compare **`llm.usage`** totals by `usage_context` (gateway) or token-report lines (markdown), keeping model and schedule fixed.
3. Turn on **caps** incrementally (`PROMOTER_LLM_*`, `AINL_BRIDGE_REPORT_MAX_CHARS`) and record deltas.
4. Prefer **rolling budget** + **embedding top-k** reads over bulk `memory.list` into LLM prompts.

## Sizing checklist (`AINL_BRIDGE_REPORT_MAX_CHARS` + `AINL_EMBEDDING_INDEX_NAMESPACE`)

Use **evidence from your machine** (not global monthly token totals) before locking in production defaults.

1. **One-shot probe (recommended)** — read-only; prints SQLite **namespace counts**, sizes of recent `## Token Usage Report` sections in daily markdown, and a **suggested** report cap (~2× max observed):

   ```bash
   ainl bridge-sizing-probe
   ainl bridge-sizing-probe --json
   # same script (also: ainl-bridge-sizing-probe --help)
   python3 scripts/bridge_sizing_probe.py --json
   ```

   Respects `AINL_MEMORY_DB`, `OPENCLAW_MEMORY_DIR` / `OPENCLAW_DAILY_MEMORY_DIR`, `OPENCLAW_WORKSPACE` like the bridge. CI runs `tests/test_bridge_sizing_probe.py` as part of the **core** pytest profile (`scripts/run_test_profiles.py --profile core`).

2. **Namespace detail** — same data as the probe’s `by_namespace`, if you want JSON only:

   ```bash
   python3 scripts/memory_retention_report.py --json
   ```

   Set `AINL_EMBEDDING_INDEX_NAMESPACE` to the namespace that actually holds rows you want semantically searchable (often `workflow` for budget/cron state; use `intel` when that’s where your rows live — the probe’s `embedding_namespace_hint` is a tie-break when both exist).

3. **Apply** — export the env vars for the OpenClaw bridge process (or wrapper cron), restart if needed, and re-run **`python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot --dry-run`** to confirm.

## See also

- [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) — agent vs AINL roles, host contract, default loop
- [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) — safe order for caps (bridge, gateway, intelligence env)
- [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md) — vector search pilot checklist
- [`WASM_OPERATOR_NOTES.md`](WASM_OPERATOR_NOTES.md) — deterministic work in WASM
- [`TTL_MEMORY_TUNER.md`](TTL_MEMORY_TUNER.md) — TTL tuner bridge + dry-run
- [`UNIFIED_MONITORING_GUIDE.md`](UNIFIED_MONITORING_GUIDE.md) — operator cron + memory paths
- [`../openclaw/bridge/README.md`](../../openclaw/bridge/README.md) — wrapper names and env tables
- [`../getting_started/STRICT_AND_NON_STRICT.md`](../getting_started/STRICT_AND_NON_STRICT.md) — compile strictness (orthogonal to token observability)
