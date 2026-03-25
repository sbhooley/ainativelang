# Token caps — staging order (gateway, bridge, intelligence)

Use this page to turn on **hard caps** safely: one surface at a time, measure, then tighten. See also [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md).

**Bundled defaults:** named profiles (`ainl profile list`, [`AINL_PROFILES.md`](AINL_PROFILES.md)) set conservative `AINL_*` combinations without replacing gateway tuning.

## 1. Bridge markdown reports (`AINL_BRIDGE_REPORT_MAX_CHARS`)

- **What it caps:** `token_budget_report` markdown from the OpenClaw bridge adapter (not gateway chat).
- **Staging:** Start unset (no cap). Use `ainl bridge-sizing-probe --json` to sample section sizes, then set the cap to ~2× max observed.
- **Failure mode:** Reports truncate to a short “budget exhausted” stub — operators lose the long tail until they raise the cap or reduce monitor history.

## 2. Apollo / gateway promoter (`PROMOTER_LLM_*`)

Set on the process that runs `apollo-x-bot/gateway_server.py`:

| Variable | Role |
|----------|------|
| `PROMOTER_LLM_MAX_PROMPT_CHARS` | Truncate chat `messages` to the last N characters |
| `PROMOTER_LLM_MAX_COMPLETION_TOKENS` | Upper bound on completion tokens per request |
| `PROMOTER_LLM_EXTRA_BODY_JSON` / `OPENAI_CHAT_EXTRA_BODY_JSON` | Provider-specific body merge |

**Staging:** Use a **dev/staging** gateway first. Begin with a generous `MAX_PROMPT_CHARS`, then lower while watching error rates and user-visible truncation.

## 3. Intelligence programs + rolling budget (env)

| Variable | Role |
|----------|------|
| `AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE` | Set to `1` to skip merging SQLite rolling budget into `MONITOR_CACHE_JSON` `workflow.token_budget` before `run_intelligence.py` runs |
| `AINL_INTELLIGENCE_ROLLING_CONSERVATIVE_DAILY` | Default `1`: `daily_remaining` = `min(existing, weekly_remaining//7)` when both exist |

Intelligence graphs read **`R cache get "workflow" "token_budget"`**. Hydration copies **`memory` `workflow` / `budget.aggregate` / `weekly_remaining_v1`** (from `rolling_budget_publish`) into that cache key so startup/summarizer gates align with the bridge without scanning 7+ days of markdown.

### Suggested intelligence-side token caps (startup context)

These affect AINL’s LLM-facing prompt sizes (chat context injection), not bridge markdown reports:

- `AINL_STARTUP_CONTEXT_TOKEN_MIN` / `AINL_STARTUP_CONTEXT_TOKEN_MAX`: clamp for `token_aware_startup_context` token budget allocation.
  - Default min/max values are safe; profiles like `cost-tight` set an aggressive max (e.g. ~500) after measuring.
- `AINL_STARTUP_USE_EMBEDDINGS`: enables an optional embedding top-k candidate path in `token_aware_startup_context`.
  - If `AINL_EMBEDDING_MODE=stub`, AINL won’t take the embedding path and will fall back to `MEMORY.md` scanning.
  - When you set real vectors (`AINL_EMBEDDING_MODE=openai`) and index via the embedding-memory-pilot wrapper, this path can further reduce bootstrap tokens.

## Suggested order

1. Size bridge reports → set `AINL_BRIDGE_REPORT_MAX_CHARS` if needed.  
2. Enable weekly trends + `rolling_budget_publish` (live OpenClaw cron) so `weekly_remaining_v1` exists.  
3. Run `scripts/run_intelligence.py` (hydration runs automatically unless skipped).  
4. Tune gateway `PROMOTER_LLM_*` last — highest blast radius for user-facing chat.
