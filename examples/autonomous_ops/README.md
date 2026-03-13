# Autonomous Ops Example Pack

These examples demonstrate practical, self‑contained operational monitors built with AINL. They are **extension‑OpenClaw** (non‑strict) to allow pragmatic use of all available adapters (`svc`, `extras`, `tiktok`, `db`, etc.).

## Programs

| File | Purpose | Schedule |
|------|---------|----------|
| `infrastructure_watchdog.lang` | Checks `svc.caddy`, `svc.cloudflared`, `svc.maddy`, `svc.crm`; cooldown 30 min; queue “restart attempt” jobs. | Every 5 min |
| `tiktok_sla_monitor.lang` | Validates TikTok reports (<24h), video processing freshness, and DB backup mtime; cooldown 1 hour. | Every 15 min |
| `lead_quality_audit.lang` | Daily audit of leads (`db.F`), computes quality metrics, sends summary to queue. | Daily 2 AM |
| `token_cost_tracker.lang` | Polls OpenRouter usage endpoint; alerts when daily USD limit exceeded. | Hourly |
| `canary_sampler.lang` | Pings critical HTTP endpoints; tracks consecutive failures; alerts after 3 in a row. | Every 5 min |
| `token_budget_tracker.lang` | Rolling 7‑day token cost vs weekly budget; sends summary to queue. | Hourly |
| `session_continuity.lang` | Extracts user preferences from recent sessions; appends to daily log and long‑term prefs. | Every 2 hours |
| `memory_prune.lang` | Calls `memory.prune` to physically delete expired memory records; optional before/after stats. | Daily 3 AM |
| `meta_monitor.lang` | Watchdog for all monitors; alerts if any monitor heartbeat is stale (configurable module list). | Every 15 min |
| `monitor_system.lang` | Reference multi‑monitor orchestration shape (optional). | — |

## Usage

Copy any `.lang` file to your `demo/` or another active monitor directory. Ensure required adapters are enabled in `ADAPTER_REGISTRY.json`. Then either:

- Run manually: `python3 run_ainl.py path/to/file.lang`
- Add to cron: `openclaw cron add ...` with `payload.kind="agentTurn"`

Cooldown state is stored in the cache (default `/tmp/monitor_state.json`). Queue messages are handled by the existing OpenClaw notification system.

## Patterns Demonstrated

- **Snapshot → Queue:** Linear status collection followed by a single `queue.Put`.
- **Cooldown windows:** Use `cache.Get/Set` with timestamps and TTL checks.
- **Consecutive failure detection:** Increment a cached counter on failure; reset on success.
- **Adapter composition:** Combine `svc`, `extras`, `tiktok`, `db`, `http`, `core` in one program.

These are not canonical core AINL; they rely on OpenClaw‑specific extensions. For canonical examples, see `examples/status_branching.ainl` and `examples/retry_error_resilience.ainl`.