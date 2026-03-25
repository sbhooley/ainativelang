# TTL memory tuner (bridge)

**Goal:** Adjust `ttl_seconds` on **opt-in** workflow rows (tags include `ttl_managed`) based on bridge logic — shorter TTL for cold rows, extend hot ones when metadata supports it.

## Entry points

- Bridge verb: `ttl_memory_tuner_run` (see `openclaw/bridge/bridge_token_budget_adapter.py`).  
- Wrapper: `openclaw/bridge/wrappers/ttl_memory_tuner.ainl`  
- Runner: `python3 openclaw/bridge/run_wrapper_ainl.py ttl-memory-tuner --dry-run`

## Environment

| Variable | Role |
|----------|------|
| `AINL_TTL_TUNER_TAG` | Required tag on memory metadata (default `ttl_managed`) |

## Safe rollout

1. Always **`--dry-run`** first — no TTL writes.  
2. Tag a **small** set of non-critical records with `ttl_managed`.  
3. Run live on a narrow cron; monitor `memory` row counts and expiry behavior.  
4. Expand tags only after observation.

Wrong TTLs can **expire data early** — keep backups and test namespaces where possible.
