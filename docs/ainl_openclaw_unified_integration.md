# AINL · OpenClaw unified integration (adapter bridge + thin wrappers)

## Architecture boundaries (post-unification)

- **AINL canonical core** (language, compiler, graph runtime, portable examples) is defined in **`docs/AINL_CANONICAL_CORE.md`**. It must not depend on OpenClaw paths, cron payloads, or workspace memory layout.
- **OpenClaw integration** — runner, drift tooling, memory CLI, triggers, and cron/supervisor documentation — is **isolated** under **`openclaw/bridge/`**. That directory is the **single source of truth** for how OpenClaw (and OS cron) invoke AINL wrappers with `--dry-run`, dynamic adapter registration, and registry-aligned fingerprints.
- **OpenClaw MCP skill (host config)** — in-repo **`skills/openclaw/`**, **`ainl install-mcp --host openclaw`** (alias **`install-openclaw`**), **`~/.openclaw/openclaw.json`** (`mcp.servers.ainl`), **`~/.openclaw/bin/ainl-run`** — is documented in **`docs/OPENCLAW_INTEGRATION.md`** (orthogonal to **`openclaw/bridge/`** cron/memory automation).
- **ZeroClaw integration** — **ZeroClaw skill**, **`ainl install-mcp --host zeroclaw`** (alias **`install-zeroclaw`**), **`~/.zeroclaw/mcp.json`**, and **`ainl-mcp`** — is documented in **`docs/ZEROCLAW_INTEGRATION.md`** (separate from **`openclaw/bridge/`**; same AINL **`memory`** adapter as other hosts, not OpenClaw markdown).
- **`scripts/run_wrapper_ainl.py`**, **`scripts/cron_drift_check.py`**, and **`scripts/ainl_memory_append_cli.py`** remain as **thin shims** that delegate to `openclaw/bridge/` so existing automation and registry paths keep working without duplicating logic.

## Related narrative (keep in sync)

For one readable walkthrough of **four tiered state**, **SQLite `memory` vs OpenClaw daily markdown**, **MCP on OpenClaw and ZeroClaw**, and **bridge monitoring**, see **[AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents)**. Host wiring hub: **[`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)**.

This document describes the **additive** integration: Python adapters (`openclaw_memory`, `github`, `crm`, `openclaw_token_tracker`), manifest entries, thin `.ainl` wrappers under `scripts/wrappers/`, and the bridge runner under `openclaw/bridge/run_wrapper_ainl.py`. Core compiler/runtime behavior is unchanged; Advocate Suite daemon scripts are orthogonal.

## Cron governance (multi-scheduler drift)

OpenClaw cron, AINL `S core cron`, and OS schedulers can all describe “when” work runs. The same pattern works for **any** OpenClaw user: your registry, your payload fingerprints, `openclaw` on PATH (or `OPENCLAW_BIN`).

- **`tooling/cron_registry.json`** (or **`CRON_REGISTRY_PATH`**) — canonical intent per job (`execution_owner`, `openclaw_match.payload_contains` from *your* job text).
- **`openclaw/bridge/cron_drift_check.py`** (shim: **`scripts/cron_drift_check.py`**) — read-only diff vs `openclaw cron list --json` and AINL schedule modules; untracked-job heuristic is **opt-in** via registry `meta.untracked_payload_substrings` or `CRON_DRIFT_UNTRACKED_SUBSTRINGS`.

See **[`docs/CRON_ORCHESTRATION.md`](CRON_ORCHESTRATION.md)** for portable setup, agent vs AINL lanes, migration patterns, and strict flags.

## Ports and schedules (single sources)

| What | Where |
|------|--------|
| Default CRM HTTP port / base URL | `adapters/openclaw_defaults.py` (`DEFAULT_CRM_HTTP_PORT`, `DEFAULT_CRM_API_BASE`) — avoids well-known ports like **3000**, **8080**, **5000** |
| Wrapper cron expressions (AINL `S core cron`) | `modules/openclaw/cron_supervisor.ainl`, `cron_content_engine.ainl`, `cron_github_intelligence.ainl` — each file notes the matching constant in `openclaw_defaults.py` |
| Content-engine health probe URL | Frame key `crm_health_url`, set by `openclaw/bridge/run_wrapper_ainl.py` from `CRM_HEALTH_URL` or `CRM_API_BASE` + `/api/health` |

**Override** when your CRM listens elsewhere:

```bash
export CRM_API_BASE=http://127.0.0.1:YOUR_PORT
# optional explicit probe URL:
export CRM_HEALTH_URL=http://127.0.0.1:YOUR_PORT/api/health
```

## Components

| Piece | Role |
|--------|------|
| `adapters/openclaw_defaults.py` | Default CRM port/URL + `CRON_*` strings (keep in sync with `modules/openclaw/cron_*.ainl`) |
| `adapters/openclaw_memory.py` | Daily markdown append/read; `openclaw memory search --json`; search result cache in `MONITOR_CACHE_JSON` |
| `adapters/github.py` | GitHub REST (`search_repos`, `get_repo`, `create_issue`); optional `GITHUB_TOKEN`; short GET cache |
| `adapters/crm.py` | HTTP to CRM (`CRM_API_BASE`, default from `openclaw_defaults`); paths overridable via `CRM_PATH_*` |
| `adapters/openclaw_token_tracker.py` | Main-session token snapshot via `openclaw sessions`; optional `openclaw cache` persistence (`RUN` / `ReadTokenStats`) |
| `openclaw/bridge/run_wrapper_ainl.py` (shim: `scripts/run_wrapper_ainl.py`) | Registry builder; injects `crm_health_url` for `content-engine.ainl`; registers adapters; applies **budget guards** (skips non-critical wrappers when `workflow.token_budget` in `MONITOR_CACHE_JSON` is low—see below) |
| `scripts/wrappers/*.ainl` | `include` the matching `modules/openclaw/cron_*.ainl` schedule module |

## Token tracker adapter (`openclaw_token_tracker`)

Registered in **`openclaw/bridge/run_wrapper_ainl.py`** with `openclaw_memory`, `github`, and `crm`. It aggregates **main direct session** token usage (sessions whose key is `agent:main:main`) from **`openclaw sessions --json --active <minutes>`** and optionally persists JSON via **`openclaw cache set`** / **`openclaw cache get`**.

- **`RUN`** — Recompute totals and write the cache snapshot (returns a stats dict).
- **`ReadTokenStats`** — Return a cached snapshot if younger than the TTL; otherwise recompute and refresh.

**Host setup:** Set **`OPENCLAW_BIN`** to the same `openclaw` binary your host uses (defaults match other in-repo adapters). The adapter needs a CLI that implements **`sessions`**; **`cache`** get/set is required only if you want persistent snapshots between runs. If a subcommand is missing, stats/cache steps fail gracefully (empty or partial results).

| Variable | Default | Role |
|----------|---------|------|
| `TOKEN_TRACKER_CACHE_NS` | `workflow` | Namespace for `openclaw cache` snapshot |
| `TOKEN_TRACKER_CACHE_KEY` | `main_session_tokens` | Key under that namespace |
| `TOKEN_TRACKER_WINDOW_MINUTES` | `60` | Window passed to `openclaw sessions --active` |
| `TOKEN_TRACKER_CACHE_TTL` | `300` | Seconds `ReadTokenStats` treats cache as fresh |

**Manifest:** `tooling/adapter_manifest.json` → **`openclaw_token_tracker`**.

## Content-engine wrapper (model override + budget guard)

**Entry:** `scripts/wrappers/content-engine.ainl` via `python3 openclaw/bridge/run_wrapper_ainl.py content-engine`.

- **Model selection:** The program reads **`R cache get "budget" "model_override"`**. If that value is non-empty, it is used as the OpenAI chat model name; otherwise **`gpt-4o-mini`**. Your rolling-budget or operator pipeline should write `model_override` into the same monitor **`cache`** store the bridge uses (typically namespace **`workflow`**, key **`budget`** or aligned with your token-budget jobs).
- **Budget guard:** When **`MONITOR_CACHE_JSON`** contains low **`workflow.token_budget`** daily/weekly remaining figures, **`run_wrapper_ainl.py`** may **skip launching** wrappers that are not **critical**, so scheduled jobs do not spend tokens on secondary work. **`content-engine`** is **critical** (with **`token-budget-alert`**): it is **not** skipped by this guard. Thresholds: **`AINL_WRAPPER_MIN_DAILY_REMAINING`** (default `1000`), **`AINL_WRAPPER_MIN_WEEKLY_REMAINING`** (default `5000`). Optional per-wrapper JSON: **`AINL_WRAPPER_BUDGET_GUARDS_JSON`** (see `openclaw/bridge/run_wrapper_ainl.py`).

## Production monitoring stack (bridge)

These wrappers run via **`openclaw/bridge/run_wrapper_ainl.py`** and write to OpenClaw daily markdown unless `--dry-run` is set:

| Wrapper name | Schedule (in `.ainl`) | Role |
|--------------|----------------------|------|
| `token-budget-alert` | `0 23 * * *` UTC | Token usage report append to **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, optional budget Telegram (consolidated, timestamped), monitor-cache size/prune, sentinel duplicate guard for the **main** report |
| `weekly-token-trends` | `0 9 * * 0` (Sun) | Scans recent `YYYY-MM-DD.md` files, appends **`## Weekly Token Trends`** |
| `email-monitor` (optional) | `*/15 * * * *` (default) | Checks Gmail for unread emails via the `email` adapter and sends a Telegram notification if any are found. **Requires** `openclaw mail` plugin (not included in default installs). See [`docs/openclaw/EMAIL_MONITOR.md`](openclaw/EMAIL_MONITOR.md) for details and enabling instructions. Currently disabled in `run_wrapper_ainl.py` by default. |

**Rolling budget storage:** the bridge publishes the rolling aggregate primarily to SQLite **`memory_records`** (`namespace='workflow'`, `record_kind='budget.aggregate'`, `record_id='weekly_remaining_v1'`); the legacy **`weekly_remaining_v1`** *table* is bootstrapped for compatibility. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> **`ainl status`** uses **`_read_weekly_remaining_rollup`** (legacy row first, else **`memory_records`**) — canonical narrative in **[`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md)** §c. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

**Single operator guide:** [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md)  
**Token budget detail:** [`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md)  
**Bridge README:** [`openclaw/bridge/README.md`](../openclaw/bridge/README.md)

## Environment variables

- **OpenClaw CLI**: `OPENCLAW_BIN` (default matches other OpenClaw adapters in-repo). Required for **`openclaw_token_tracker`** session/cache integration.
- **Daily file location**: `OPENCLAW_MEMORY_DIR` or `OPENCLAW_WORKSPACE/memory` (default **`~/.openclaw/workspace/memory`**) so `openclaw memory search` and on-disk notes stay consistent. Each day’s file is **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**.
- **Dry run**: `AINL_DRY_RUN=1` or pass `--dry-run` to `openclaw/bridge/run_wrapper_ainl.py` (or the `scripts/` shim), or set frame key `dry_run` when embedding `RuntimeEngine`.
- **GitHub**: `GITHUB_TOKEN` or `GH_TOKEN`; `GITHUB_API_URL` if using Enterprise.
- **CRM**: `CRM_API_BASE`, `CRM_HEALTH_URL`, `CRM_PATH_GITHUB_INTEL_DIGEST`, `CRM_PATH_GITHUB_INTEL_FIND`, `CRM_PATH_LEADS_UPSERT` as needed.
- **Token tracker:** `TOKEN_TRACKER_CACHE_NS`, `TOKEN_TRACKER_CACHE_KEY`, `TOKEN_TRACKER_WINDOW_MINUTES`, `TOKEN_TRACKER_CACHE_TTL` (see **Token tracker adapter** above).
- **Wrapper budget guards** (bridge skip logic): `AINL_WRAPPER_MIN_DAILY_REMAINING`, `AINL_WRAPPER_MIN_WEEKLY_REMAINING`, `AINL_WRAPPER_BUDGET_GUARDS_JSON` (see **Content-engine wrapper** above).

## Testing with `--dry-run`

```bash
cd /path/to/AI_Native_Lang
python3 openclaw/bridge/run_wrapper_ainl.py supervisor --dry-run
python3 openclaw/bridge/run_wrapper_ainl.py github-intelligence --dry-run
python3 openclaw/bridge/run_wrapper_ainl.py full-unification --dry-run
AINL_DRY_RUN=1 python3 openclaw/bridge/ainl_memory_append_cli.py "probe"
```

(`scripts/run_wrapper_ainl.py` and `scripts/ainl_memory_append_cli.py` are shims to the same code.)

`openclaw/bridge/run_wrapper_ainl.py` sets frame `dry_run` and `AINL_DRY_RUN` so the **new** adapters skip file writes, GitHub mutations, CRM POSTs, and the `openclaw memory search` subprocess (returns `[]` for search). `read_today` still reads the existing file if present (read-only).

Wrappers omit `QueuePut` by default so dry-runs do not hit Telegram; add `QueuePut notify <var>` after the `openclaw_memory` step when you want the same delivery path as `intelligence_digest.lang`.

The bridge runner sets `OPENROUTER_API_KEY` to a placeholder if unset so `openclaw_monitor_registry()` can construct `WebAdapter` (existing behavior). Set a real key before running programs that call `R web search`.

## One-liner CLI helper (external agents)

```bash
python3 /path/to/AI_Native_Lang/openclaw/bridge/ainl_memory_append_cli.py "message from any agent"
```

Optional alias:

```bash
alias ainl-memory-append='python3 /path/to/AI_Native_Lang/openclaw/bridge/ainl_memory_append_cli.py'
# then:
ainl-memory-append "logged to today's OpenClaw-style memory file"
```

## OpenClaw cron (session continuity)

Cron strings should match the included `modules/openclaw/cron_*.ainl` files (and `adapters/openclaw_defaults.py` for Python-side tooling).

OpenClaw’s `cron add` surface evolves by version; the intent is **one session key** so token/memory context stays stable (here: `ainl-advocate`). Adjust flags to match your installed CLI (`openclaw cron add --help`).

**Supervisor** (every 15 minutes):

```bash
openclaw cron add \
  --name ainl-wrapper-supervisor \
  --cron "*/15 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py supervisor" \
  --description "AINL supervisor wrapper"
```

**Content-engine** (every 30 minutes):

```bash
openclaw cron add \
  --name ainl-wrapper-content-engine \
  --cron "*/30 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py content-engine" \
  --description "AINL content-engine wrapper"
```

**GitHub intelligence** (every 6 hours at :15):

```bash
openclaw cron add \
  --name ainl-wrapper-github-intelligence \
  --cron "15 */6 * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py github-intelligence" \
  --description "AINL GitHub intelligence wrapper"
```

If your CLI uses `--session` instead of `--session-key`, substitute per `openclaw cron add --help`. Some installs route “run this shell command” via **agentTurn** payloads in the operator UI rather than `--message`; keep the same `python3 .../openclaw/bridge/run_wrapper_ainl.py <name>` command.

## Migration notes (retiring Node scripts later)

1. **Overlap period**: Keep Advocate `daemon.sh` / Node jobs running; add OpenClaw cron entries that call `openclaw/bridge/run_wrapper_ainl.py` on a staggered schedule.
2. **CRM routes**: Point `CRM_PATH_*` at the same URLs your Node clients use once confirmed (or add thin HTTP routes in CRM that mirror the Node payload shapes). Bind the CRM process to the same non-default port you configure in `CRM_API_BASE`, or override env to match your listener.
3. **Cutover**: Disable duplicate Node cron entries when wrappers prove stable; retain Node for only-if-needed endpoints (e.g. heavy ETL) behind feature flags.
4. **Strict compile**: These wrappers are built with `strict_mode=False`. If you later enable strict mode, add matching `ADAPTER_EFFECT` entries in `tooling/effect_analysis.py` for each `adapter.VERB` key.

## Token-aware startup context optimization

The **token_aware_startup_context** wrapper automatically generates a compact `session_context.md` for OpenClaw session bootstrapping, reducing token usage on every new session.

### What it does

- Reads your full `MEMORY.md`
- Filters for high-signal lines (decisions, preferences, todos, lessons, settings)
- Respects a configurable token budget (default: 5% of remaining daily budget, clamped **100–150** tokens, typically **~140**)
- Writes optimized context to `.openclaw/bootstrap/session_context.md`
- Persists generation stats to AINL memory and cache

This automation replaces manual curation of `session_context.md`, making _you_ (the AI agent) the maintainer. With a target of **100–150** tokens (typical ~115), it reduces session bootstrap tokens from ~3,200 (full MEMORY.md) by **>96%**, preventing context max-outs during high-frequency usage.

### Installation (v1.8.0+)

**Quickest path:** Run the all-in-one setup script:

```bash
cd AI_Native_Lang/scripts
./setup_ainl_integration.sh --with-cron
```

This performs all steps below automatically:
- Applies OpenClaw config patch (env vars, compaction) including setting `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1`
- Registers wrappers (including token-aware-startup)
- Adds cron jobs (token-aware startup, token budget alerts, weekly trends)
- Restarts gateway

See [`scripts/setup_ainl_integration.sh`](../../scripts/setup_ainl_integration.sh) for details.

**Manual installation:**

1. Copy the wrapper to the bridge wrappers directory:
   ```bash
   cp AI_Native_Lang/intelligence/token_aware_startup_context.lang AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl
   ```

2. Register the wrapper in `openclaw/bridge/run_wrapper_ainl.py` (if not already present):
   ```python
   "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",
   ```

3. **Set environment variable** (OpenClaw >= 2026.3.22; native support):
   Ensure `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1` is set in OpenClaw’s environment (the setup script does this via `gateway config.patch`). For manual setup:
   ```bash
   openclaw gateway config.patch '{"env":{"vars":{"OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT":"1"}}}'
   openclaw gateway restart
   ```
   *For OpenClaw versions older than 2026.3.22, use the legacy patch script `scripts/patch_bootstrap_loader.sh` (not recommended; upgrade OpenClaw).*

4. Apply the configuration patch (or set manually):
   ```bash
   openclaw gateway config.patch AI_Native_Lang/scripts/config_patch_ainl_integration.json
   ```
   This sets:
   - `AINL_STARTUP_CONTEXT_TOKEN_MIN=100`, `MAX=200`
   - `AINL_STARTUP_USE_EMBEDDINGS=1`, `EMBEDDING_MODE=lite`
   - `AINL_EXECUTION_MODE=graph-preferred`
   - `agents.defaults.compaction.reserveTokens=30000`

5. Add cron job (if not using the setup script):
   ```bash
   openclaw cron add \
     --name "Token-Aware Startup Context" \
     --cron "*/15 * * * *" \
     --session-key "agent:default:ainl-advocate" \
     --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py token-aware-startup" \
     --description "Generates optimized session_context.md for faster boot"
   ```

6. Test:
   ```bash
   python3 openclaw/bridge/run_wrapper_ainl.py token-aware-startup --dry-run
   ```
   Inspect `.openclaw/bootstrap/session_context.md` to verify size (~100–150 tokens).

### Verification

- Check the file modification time updates with each run.
- Compare token counts: the generated file should be ~100–150 tokens (~13–18 lines, ~500–600 bytes). Target typically ~140 tokens.
- Ensure your regular sessions now bootstrap with the smaller context (observe token count in `/status`; ~140 tokens expected).

### Notes

- The wrapper uses the `openclaw_monitor_registry()` adapters; no extra dependencies required.
- The program respects the `AINL_FS_ROOT` environment (set automatically by the registry to your OpenClaw workspace) so it reads `MEMORY.md` and writes to the correct `.openclaw/bootstrap` path.
- The current wrapper build forces filesystem-only selection (`useEmb=false`) for stability; embedding flags are reserved for a future re-enable pass.

**See also:** Standalone documentation in `docs/openclaw/TOKEN_AWARE_STARTUP_CONTEXT.md`.

## Files touched in the repo

- **Bridge / integration**: `openclaw/bridge/*` (runner, drift check, memory CLI, triggers), `scripts/run_wrapper_ainl.py` + `scripts/cron_drift_check.py` + `scripts/ainl_memory_append_cli.py` (shims), `scripts/wrappers/*.ainl`, `examples/openclaw_full_unification.ainl`, `openclaw/bridge/README.md`, [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md) (unified monitoring hub), this doc, **plus**: `openclaw/bridge/wrappers/token_aware_startup_context.ainl` (new wrapper).
- **Adapters / modules**: `adapters/openclaw_memory.py`, `adapters/github.py`, `adapters/crm.py`, `adapters/openclaw_defaults.py`, `modules/openclaw/cron_*.ainl`.
- **Updated**: `tooling/adapter_manifest.json` (adapter entries including `crm` notes).

No other existing files were modified.
