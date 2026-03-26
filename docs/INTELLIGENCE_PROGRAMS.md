# Intelligence programs (`intelligence/*.lang`)

AINL sources under `intelligence/` support **OpenClaw-style** automation: memory compaction, session signals, token-aware bootstrap context, and scheduled digests. They are **examples / operator programs** — not part of the core language spec. **ZeroClaw** users usually integrate via **`docs/ZEROCLAW_INTEGRATION.md`** (skill + **`ainl-mcp`**), not this monitor registry layout.

**Authoring note:** Before `Call genmem/WRITE`, `Call accmem/LACCESS_READ`, or `R memory put`, bind contract fields with **`Set`** (`Set memory_namespace "workflow"`, `Set memory_kind "…"`, …), not **`X`**. The `X` op requires a real function name (`get`, `core.substr`, …); see the callout under **`X`** in **`docs/AINL_SPEC.md`** §2.3.

**Graph runtime:** Intelligence programs run on the compiler-emitted **graph** by default. Do not use **`X dst {…}`** JSON object literals (use **`core.parse`**, **`obj`/`put`**, or **`arr`** — see **`intelligence/token_aware_startup_context.lang`** and **`modules/common/generic_memory.ainl`**). Do not use **`J OtherLabel`** to chain labels (**`J`** returns a value; use **`Call`** or same-label fall-through). For **`memory.list`**, use **`null`** for an omitted **`record_id_prefix`**, not **`""`**. **`metadata.valid_at`** must be an RFC3339 string (e.g. **`R core iso`**) when using the memory contract. Run tests with **`./.venv-py310/bin/python -m pytest`** per **`docs/INSTALL.md`**.

## Programs

| File | Role |
|------|------|
| `intelligence_digest.lang` | Scheduled web + TikTok snapshot, cache + memory + notify (see `openclaw/INTELLIGENCE_DIGEST.md`) |
| `memory_consolidation.lang` | Keyword-based promotion from `memory/*.md` into `MEMORY.md` (no LLM) |
| `proactive_session_summarizer.lang` | Summarize prior-day logs via OpenRouter; writes `MEMORY.md`; needs `OPENROUTER_API_KEY` + `http` allowlist |
| `token_aware_startup_context.lang` | Builds compact `.openclaw/bootstrap/session_context.md` from `MEMORY.md` under a token budget |
| `token_aware_startup_context2.lang` | Variant bootstrap writer (same general pattern) |
| `session_continuity_enhanced.lang` | Lists `session` memory keys, heartbeat + notify (monitoring posture) |
| `store_baseline.lang` | One-shot seed into `memory` (`intel` / baseline) |
| `test_split.lang` | Small harness for split/len-style checks |
| `infrastructure_watchdog.lang` | Service health checks + optional notify path (operator-tuned; pair with your gateway / bridge allowlists) |
| `signature_enforcer.py` | Optional signature metadata checks (`# signature: ...`) + bounded retry helper for `ptc_runner` |
| `trace_export_ptc_jsonl.py` | Exports AINL trajectory JSONL to PTC-compatible JSONL shape |

## Local runner

`scripts/run_intelligence.py` compiles and runs selected programs with the OpenClaw monitor adapter registry (for hosts that mirror that layout):

```bash
# from repo root, with project on PYTHONPATH / editable install
python3 scripts/run_intelligence.py context
python3 scripts/run_intelligence.py summarizer --trace
python3 scripts/run_intelligence.py consolidation
python3 scripts/run_intelligence.py continuity
python3 scripts/run_intelligence.py signature_enforcer --dry-run
python3 scripts/run_intelligence.py trace_export_ptc_jsonl --dry-run
python3 scripts/run_intelligence.py all
```

**Rolling budget → cache:** On each non–dry-run start, the runner merges SQLite **`workflow` / `budget.aggregate` / `weekly_remaining_v1`** (from bridge `rolling_budget_publish`) into **`workflow`/`token_budget`** in `MONITOR_CACHE_JSON`, so startup and summarizer gates align with weekly trends without scanning days of markdown. See **`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`** and **`docs/operations/TOKEN_CAPS_STAGING.md`**. JSON output includes **`budget_hydrate`**.

Enable the same adapters and paths your production gateway uses (`fs`, `cache`, `http`, `memory`, `queue`, etc.); see `docs/INSTALL.md` and `docs/reference/ADAPTER_REGISTRY.md`.

## PTC Reliability Patterns

For PTC-style reliability overlays (all opt-in), use:

- `intelligence/signature_enforcer.py`
  - parses optional `# signature: ...` metadata
  - validates result shape/types
  - supports bounded retry helper for `ptc_runner`
- `intelligence/trace_export_ptc_jsonl.py`
  - converts AINL trajectory JSONL into PTC-compatible JSONL
  - strips `_`-prefixed keys during export (context firewall)

Reference end-to-end flow:

- `docs/adapters/PTC_RUNNER.md` → **Canonical End-to-End Example**

## Host responsibilities

- **Cron / scheduler:** programs declare `S` schedules; the host must trigger runs.
- **Prompt injection:** token-aware output is only useful if the host loads `session_context.md` / `MEMORY.md` into the agent context. Prefer **curated bootstrap** over full `MEMORY.md` when startup context has run — see **`docs/operations/AGENT_AINL_OPERATING_MODEL.md`** (host contract).
- **Secrets:** summarizer and digest flows need env vars (e.g. `OPENROUTER_API_KEY`) where applicable.

## See also

- [`operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md) — recommended cron, paths, and **`budget_hydrate`** checks for OpenClaw-style hosts
- [`agent_reports/README.md`](../agent_reports/README.md) — operator field reports
- [`docs/RUNTIME_COMPILER_CONTRACT.md`](RUNTIME_COMPILER_CONTRACT.md)
- [`docs/OPENCLAW_ADAPTERS.md`](OPENCLAW_ADAPTERS.md)
