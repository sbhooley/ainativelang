# Autonomous Ops Monitors — Index

**Last updated:** 2026-03-12

This document provides a quick reference for all AINL autonomous operations monitors deployed in OpenClaw.

---

## Table

| Monitor | Schedule | Purpose | Key Metrics | Memory Schema | Runner | Envelope | Status |
|---------|----------|---------|-------------|---------------|--------|----------|--------|
| `infrastructure_watchdog` | every 5 min | Checks caddy, cloudflared, maddy, CRM; auto‑restarts down services | service statuses, restart count 24h | `ops.infrastructure.restart` (event) | `scripts/run_infrastructure_watchdog.py` | ✅ v1.0 | Active |
| `tiktok_sla_monitor` | every 15 min | TikTok pipeline SLA: reports freshness, video processed, backup freshness | `recent_count`, `video_fresh`, `backup_fresh`, `breaches_24h` | `ops.tiktok_sla.breach` (event) | `scripts/run_tiktok_sla_monitor.py` | ✅ v1.0 | Active |
| `canary_sampler` | every 5 min | HTTP endpoint canary; slow response detection | `any_breach`, per‑target `slow`, `slow_24h` | `ops.canary.slow` (event) | `scripts/run_canary_sampler.py` | ✅ v1.0 | Active |
| `token_cost_tracker` | hourly | OpenRouter token spending vs budget | daily cost, weekly cost % of budget | `workflow.token_cost_state` (daily summary) | `scripts/run_token_cost_tracker.py` | ✅ v1.0 | Active |
| `lead_quality_audit` | daily 2 AM | Lead data completeness (phone, website, rating, reviews) | daily counts, 7‑day rolling averages, drop flags | `workflow.lead_quality_audit.daily` (daily summary) | `scripts/run_lead_quality_audit.py` | ✅ v1.0 | Active |
| `token_budget_tracker` | hourly | Rolling 7‑day token cost vs weekly budget | week cost, week tokens, pct used | reads `workflow.token_cost_state` | `scripts/run_token_budget_tracker.py` | ✅ v1.0 | Active |
| `session_continuity` | every 2 hours | Extract user preferences from recent sessions; append daily log | sessions considered, preferences captured | `daily_log.note` (append), `long_term.user_preference` (prefs) | `scripts/run_session_continuity.py` | ✅ v1.0 | Active |
| `memory_prune` | daily 3 AM | Physical deletion of expired memory records | `pruned_records`, before/after stats | — | `scripts/run_memory_prune.py` | ✅ v1.0 | Active |
| `meta_monitor` | every 15 min | Watchdog for the monitors themselves; alerts if any monitor is stale | `monitors_ok`, `monitors_stale`, `stale_details` | reads cache keys `monitor_heartbeat.*` | `scripts/run_meta_monitor.py` | ✅ v1.0 | Active |

---

## Notes

- All monitors use the **Standardized Health Envelope** (version 1.0) for `queue` messages.
- Configuration can be externalized via `memory` records under `config.<module>`.
- Each monitor writes a heartbeat to `cache` with key `monitor_heartbeat.<module>` upon successful completion, enabling `meta_monitor`.
- Memory records use sensible TTLs (7–90 days) to bound retention; `memory_prune` enforces physical cleanup.
- Runner scripts are located in `scripts/run_*.py` and are added to OpenClaw cron with `openclaw cron add`.
- **For agents implementing or changing monitors:** Follow `docs/BOT_ONBOARDING.md` and `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` before coding.

---

## Implementation Docs

- General: `openclaw/AUTONOMOUS_OPS_EXTENSION_IMPLEMENTATION.md`
- Updates:
  - `openclaw/TOKEN_COST_TRACKER_UPDATE.md`
  - `openclaw/INFRASTRUCTURE_WATCHDOG_UPDATE.md`
  - `openclaw/CANARY_SAMPLER_UPDATE.md`
  - `openclaw/LEAD_QUALITY_AUDIT_UPDATE.md`
  - `openclaw/TIKTOK_SLA_MONITOR_UPDATE.md`
- New programs:
  - `openclaw/MEMORY_PRUNE_IMPLEMENTATION.md`
  - `openclaw/META_MONITOR_IMPLEMENTATION.md`
  - `openclaw/SESSION_CONTINUITY_IMPLEMENTATION.md`
  - `openclaw/TOKEN_BUDGET_TRACKER_IMPLEMENTATION.md`

---

## Strict‑Mode Roadmap

Current autonomous ops programs use `strict_mode=False` due to reliance on `X` ops and split `R` calls. A future conversion plan will migrate each to strict mode once the necessary IR features are stabilized. See `openclaw/AUTONOMOUS_OPS_EXTENSION_IMPLEMENTATION.md` for details.
