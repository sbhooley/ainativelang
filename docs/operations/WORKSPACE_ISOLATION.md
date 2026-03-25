# Workspace isolation (multi-user / multi-tenant)

When many users or agents share a machine, **path collisions** cause cross-talk and leaks. Treat each **workspace** as a unit with its own state.

## Quick pin (one workspace)

From the repo root, anchor everything on **`OPENCLAW_WORKSPACE`** (default `~/.openclaw/workspace`):

```bash
export OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
. tooling/openclaw_workspace_env.example.sh
eval "$(ainl profile emit-shell openclaw-default)"
```

That sets **`OPENCLAW_MEMORY_DIR`**, **`AINL_FS_ROOT`**, **`AINL_MEMORY_DB`**, **`MONITOR_CACHE_JSON`**, **`AINL_EMBEDDING_MEMORY_DB`**, and **`AINL_IR_CACHE_DIR`** consistently under the same tree (creates **`$OPENCLAW_WORKSPACE/.ainl/`** for SQLite + JSON). Adjust only what you measure after `ainl bridge-sizing-probe` / live runs.

**`budget_hydrate` check:** After `scripts/run_intelligence.py` runs (non–dry-run), JSON includes **`budget_hydrate`**. **`skipped` + `reason: no_rolling_record`** is normal until the bridge has published **`workflow` / `budget.aggregate` / `weekly_remaining_v1`** (e.g. via weekly trends + `rolling_budget_publish`). Once that row exists, expect **`ok: true`** and merged keys — not permanently skipped.

## Separate these per workspace

| Surface | Typical env | Notes |
|---------|-------------|--------|
| SQLite memory | `AINL_MEMORY_DB` | Never share across tenants |
| Embedding sidecar | `AINL_EMBEDDING_MEMORY_DB` | Index is per workspace |
| OpenClaw daily markdown | `OPENCLAW_MEMORY_DIR` / `OPENCLAW_WORKSPACE` | Daily `YYYY-MM-DD.md` |
| Monitor / cache JSON | `MONITOR_CACHE_JSON` | Includes `workflow.token_budget` |
| FS sandbox | `AINL_FS_ROOT` | Intelligence programs read/write under this root |
| IR cache | `AINL_IR_CACHE_DIR` | Safe to share read-only; separate dirs avoid stampede |

## Anti-patterns

- **Global `/tmp/ainl_memory.sqlite3`** for more than one production workspace without a naming prefix.
- **One `MONITOR_CACHE_JSON`** for unrelated agents (budget and cache lines mix).
- **Embedding index** built from one DB and queried against another.

## SaaS-style deployments

If you later ship a hosted product: enforce **prefix paths** or **per-tenant databases** at the API layer; never rely on “defaults” in a shared container without namespacing.

## See also

- [`AINL_PROFILES.md`](AINL_PROFILES.md) — named defaults without mixing tenants
- [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) — artifact paths
