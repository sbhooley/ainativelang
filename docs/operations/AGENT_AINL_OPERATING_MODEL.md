# Agent + AINL operating model (long-term)

This page fixes **roles**, **defaults**, and **evidence** for humans and coding agents that use AINL alongside OpenClaw (or other hosts). It complements [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) (where signals live) and [`AINL_PROFILES.md`](AINL_PROFILES.md) (named env bundles).

## Two roles

| Role | Owns | Good fit |
|------|------|----------|
| **AINL** | Compiled graphs, adapters, monitors, budgets, tested pipelines | Cron, guardrails, repeatable transforms, retrieval pilots |
| **Agent** | Planning, synthesis, ambiguous tradeoffs, human coordination | Exploration, prioritization, “what good looks like” |

**Push down** into AINL what benefits from **structure, tests, and schedules**. **Keep up** judgment until a pattern is stable enough to formalize.

## Host contract (highest leverage)

Curated artifacts only help if the **host loads them**:

- Prefer **`.openclaw/bootstrap/session_context.md`** (or equivalent) over dumping full **`MEMORY.md`** when token-aware startup has run.
- Prefer **rolling budget keys** and **`workflow`/`token_budget`** (after hydration) over re-parsing long markdown windows for gates.

If the scheduler never runs intelligence programs, or the UI never reads bootstrap output, **token cost stays high** regardless of AINL quality.

## Default operational loop

Use this order unless measurement says otherwise:

1. **Profiles** — `ainl profile list` / [`AINL_PROFILES.md`](AINL_PROFILES.md); isolate paths per workspace — [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md).
2. **Observability** — identify which **layer** dominates spend — [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md).
3. **Rolling budget + hydration** — bridge publishes the rolling aggregate to **`memory_records`** (`workflow` / `budget.aggregate` / record id **`weekly_remaining_v1`**); `run_intelligence.py` merges into cache — [`INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md), [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md). <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> A legacy **`weekly_remaining_v1`** SQLite table may still exist from install; **`ainl status`** prefers it when non-null, else reads **`weekly_remaining_tokens`** from the memory row. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->
4. **Caps** — bridge (`AINL_BRIDGE_REPORT_MAX_CHARS`) then gateway (`PROMOTER_LLM_*`) — [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md).
5. **Intelligence programs** — token-aware startup + summarizer on a real schedule.
6. **Optional accelerants** — one path at a time: embedding pilot — [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md); WASM — [`WASM_OPERATOR_NOTES.md`](WASM_OPERATOR_NOTES.md); TTL — [`TTL_MEMORY_TUNER.md`](TTL_MEMORY_TUNER.md).

## Automate vs. pause

| Automate | Pause / measure first |
|----------|------------------------|
| Scheduled context build, summarization, rolling publish | Provider-only “sparse attention” and similar unless documented for your API |
| Index refresh where you opted in | One global cap for every feature without staging |
| Cap enforcement at bridge/gateway | WASM rewrites of hot paths without traces |

## Agent habits (checklist)

Before loading or suggesting **large** context:

1. Check **`budget_hydrate`** output from `scripts/run_intelligence.py` (JSON) or cache `workflow`/`token_budget`.
2. Use **`ainl bridge-sizing-probe`** when tuning report caps.
3. Prefer **rolling budget JSON** / **memory.get** on aggregate keys over scanning many daily files in the model prompt.

## North star

**Evidence over aspiration:** every change should be checkable against real signals (gateway usage, markdown heuristics, memory operations, bridge reports) — not against headline savings alone.

## See also

- [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) — OpenClaw reference bundle
- [`../getting_started/HOST_MCP_INTEGRATIONS.md`](../getting_started/HOST_MCP_INTEGRATIONS.md) — install-mcp hosts
