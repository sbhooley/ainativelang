# AINL · OpenClaw unified integration (adapter bridge + thin wrappers)

## Architecture boundaries (post-unification)

- **AINL canonical core** (language, compiler, graph runtime, portable examples) is defined in **`docs/AINL_CANONICAL_CORE.md`**. It must not depend on OpenClaw paths, cron payloads, or workspace memory layout.
- **OpenClaw integration** — runner, drift tooling, memory CLI, triggers, and cron/supervisor documentation — is **isolated** under **`openclaw/bridge/`**. That directory is the **single source of truth** for how OpenClaw (and OS cron) invoke AINL wrappers with `--dry-run`, dynamic adapter registration, and registry-aligned fingerprints.
- **OpenClaw MCP skill (host config)** — in-repo **`skills/openclaw/`**, **`ainl install-mcp --host openclaw`** (alias **`install-openclaw`**), **`~/.openclaw/openclaw.json`** (`mcpServers.ainl`), **`~/.openclaw/bin/ainl-run`** — is documented in **`docs/OPENCLAW_INTEGRATION.md`** (orthogonal to **`openclaw/bridge/`** cron/memory automation).
- **ZeroClaw integration** — **ZeroClaw skill**, **`ainl install-mcp --host zeroclaw`** (alias **`install-zeroclaw`**), **`~/.zeroclaw/mcp.json`**, and **`ainl-mcp`** — is documented in **`docs/ZEROCLAW_INTEGRATION.md`** (separate from **`openclaw/bridge/`**; same AINL **`memory`** adapter as other hosts, not OpenClaw markdown).
- **`scripts/run_wrapper_ainl.py`**, **`scripts/cron_drift_check.py`**, and **`scripts/ainl_memory_append_cli.py`** remain as **thin shims** that delegate to `openclaw/bridge/` so existing automation and registry paths keep working without duplicating logic.

## Related narrative (keep in sync)

For one readable walkthrough of **four tiered state**, **SQLite `memory` vs OpenClaw daily markdown**, **MCP on OpenClaw and ZeroClaw**, and **bridge monitoring**, see **[AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents)**. Host wiring hub: **[`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)**.

This document describes the **additive** integration: Python adapters (`openclaw_memory`, `github`, `crm`), manifest entries, thin `.ainl` wrappers under `scripts/wrappers/`, and the bridge runner under `openclaw/bridge/run_wrapper_ainl.py`. Core compiler/runtime behavior is unchanged; Advocate Suite daemon scripts are orthogonal.

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
| `openclaw/bridge/run_wrapper_ainl.py` (shim: `scripts/run_wrapper_ainl.py`) | Registry builder + injects `crm_health_url` into the frame for `content-engine.ainl` |
| `scripts/wrappers/*.ainl` | `include` the matching `modules/openclaw/cron_*.ainl` schedule module |

## Production monitoring stack (bridge)

These wrappers run via **`openclaw/bridge/run_wrapper_ainl.py`** and write to OpenClaw daily markdown unless `--dry-run` is set:

| Wrapper name | Schedule (in `.ainl`) | Role |
|--------------|----------------------|------|
| `token-budget-alert` | `0 23 * * *` UTC | Token usage report append to **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, optional budget Telegram (consolidated, timestamped), monitor-cache size/prune, sentinel duplicate guard for the **main** report |
| `weekly-token-trends` | `0 9 * * 0` (Sun) | Scans recent `YYYY-MM-DD.md` files, appends **`## Weekly Token Trends`** |

**Single operator guide:** [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md)  
**Token budget detail:** [`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md)  
**Bridge README:** [`openclaw/bridge/README.md`](../openclaw/bridge/README.md)

## Environment variables

- **OpenClaw CLI**: `OPENCLAW_BIN` (default matches other OpenClaw adapters in-repo).
- **Daily file location**: `OPENCLAW_MEMORY_DIR` or `OPENCLAW_WORKSPACE/memory` (default **`~/.openclaw/workspace/memory`**) so `openclaw memory search` and on-disk notes stay consistent. Each day’s file is **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**.
- **Dry run**: `AINL_DRY_RUN=1` or pass `--dry-run` to `openclaw/bridge/run_wrapper_ainl.py` (or the `scripts/` shim), or set frame key `dry_run` when embedding `RuntimeEngine`.
- **GitHub**: `GITHUB_TOKEN` or `GH_TOKEN`; `GITHUB_API_URL` if using Enterprise.
- **CRM**: `CRM_API_BASE`, `CRM_HEALTH_URL`, `CRM_PATH_GITHUB_INTEL_DIGEST`, `CRM_PATH_GITHUB_INTEL_FIND`, `CRM_PATH_LEADS_UPSERT` as needed.

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

## Files touched in the repo

- **Bridge / integration**: `openclaw/bridge/*` (runner, drift check, memory CLI, triggers), `scripts/run_wrapper_ainl.py` + `scripts/cron_drift_check.py` + `scripts/ainl_memory_append_cli.py` (shims), `scripts/wrappers/*.ainl`, `examples/openclaw_full_unification.ainl`, `openclaw/bridge/README.md`, [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md) (unified monitoring hub), this doc.
- **Adapters / modules**: `adapters/openclaw_memory.py`, `adapters/github.py`, `adapters/crm.py`, `adapters/openclaw_defaults.py`, `modules/openclaw/cron_*.ainl`.
- **Updated**: `tooling/adapter_manifest.json` (adapter entries including `crm` notes).

No other existing files were modified.
