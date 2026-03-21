# Newly Implemented AINL Programs (2026-03-14)

This document lists the 12 AINL monitoring programs implemented on 2026-03-14. For each program, we provide:

- **Purpose**: What it monitors and why
- **File locations**: Where the `.lang` source and runner script live
- **Cron schedule**: When it runs
- **Key adapters used**: `db`, `memory`, `email`, `queue`, `core`, etc.
- **Alert condition**: When a Telegram notification is sent
- **Memory integration**: What records are written for trending

---

## CRM & Leads

### 1. Lead Aging
- **Purpose**: Detect leads that have been in the system >30 days without converting (status not 'won' or 'lost'), so they can be re-engaged or cleaned.
- **Files**:
  - Source: `AI_Native_Lang/demo/lead_aging.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/lead_aging.lang`
  - Runner: `scripts/run_lead_aging.py`
- **Cron**: Daily at 02:00 America/Chicago
- **Adapters**: `db.F` (query `Lead`), `memory.put`, `email.G` (or `queue.Put` depending on template)
- **Alert if**: Any leads >30d old and status not 'won'/'lost' (count > 0)
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.lead_aging"`
  - Payload: `{ "stale_count": int, "checked_at": now_iso, "threshold_days": 30 }`
  - TTL: 90 days

### 2. Lead Score Drift
- **Purpose**: Compare average lead score over the last 7 days to the previous 7-day baseline; alert if drop >15%, indicating scoring model or lead quality degradation.
- **Files**:
  - Source: `AI_Native_Lang/demo/lead_score_drift.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/lead_score_drift.lang`
  - Runner: `scripts/run_lead_score_drift.py`
- **Cron**: Daily at 03:00 America/Chicago
- **Adapters**: `db.F` (query `Lead` with `score` field), `core` arithmetic, `memory.put`, `email.G`
- **Alert if**: `(baseline_avg - recent_avg) / baseline_avg > 0.15`
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.lead_score_drift"`
  - Payload: `{ "baseline_avg": float, "recent_avg": float, "pct_drop": float, "ts": now_iso }`
  - TTL: 90 days

### 3. Missing Fields
- **Purpose**: Track data completeness for required lead fields (phone, email, website). Alert if >5% of leads are missing any of these fields.
- **Files**:
  - Source: `AI_Native_Lang/demo/missing_fields.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/missing_fields.lang`
  - Runner: `scripts/run_missing_fields.py`
- **Cron**: Daily at 04:00 America/Chicago
- **Adapters**: `db.F`, `core` math, `memory.put`, `email.G`
- **Alert if**: For any of `phone`, `email`, `website`, missing percentage > 5%
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.missing_fields"`
  - Payload: `{ "missing_phone_pct": float, "missing_email_pct": float, "missing_website_pct": float, "total_leads": int, "ts": now_iso }`
  - TTL: 90 days

### 4. Duplicate Detection
- **Purpose**: Find leads sharing the same phone number or email address (potential duplicates) and report them for review/merging.
- **Files**:
  - Source: `AI_Native_Lang/demo/duplicate_detection.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/duplicate_detection.lang`
  - Runner: `scripts/run_duplicate_detection.py`
- **Cron**: Weekly (Sundays) at 02:30 America/Chicago
- **Adapters**: `db.F` (query `Lead`), pairwise comparison loop, `memory.put`, `email.G`
- **Alert if**: Any duplicate sets found (count > 0)
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.duplicate_detection"`
  - Payload: `{ "duplicate_sets": int, "total_duplicates": int, "ts": now_iso }`
  - TTL: 90 days

---

## Finance

### 5. Invoice Aging
- **Purpose**: Identify unpaid invoices >30 days overdue and sum the amount owed; highlight cash flow risk.
- **Files**:
  - Source: `AI_Native_Lang/demo/invoice_aging.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/invoice_aging.lang`
  - Runner: `scripts/run_invoice_aging.py`
- **Cron**: Daily at 05:00 America/Chicago
- **Adapters**: `db.F` (query `Invoice` with `status`, `due_date`, `amount`), `memory.put`, `email.G`
- **Alert if**: Any invoice with `status=' unpaid'` and `due_date` >30 days ago; also report total overdue amount
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.invoice_aging"`
  - Payload: `{ "overdue_count": int, "overdue_amount": float, "ts": now_iso }`
  - TTL: 90 days

### 6. Revenue Forecast
- **Purpose**: Sum today's paid invoices and compare to a daily target (configurable via memory). Alert if <80% of target.
- **Files**:
  - Source: `AI_Native_Lang/demo/revenue_forecast.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/revenue_forecast.lang`
  - Runner: `scripts/run_revenue_forecast.py`
- **Cron**: Daily at 06:00 America/Chicago
- **Adapters**: `db.F` (query `Invoice`), `memory.get` (read `config.revenue_daily_target`), `core` math, `memory.put`, `email.G`
- **Alert if**: `today_paid < 0.8 * daily_target`
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.revenue_forecast"`
  - Payload: `{ "today_paid": float, "daily_target": float, "pct_of_target": float, "ts": now_iso }`
  - TTL: 90 days

---

## Marketing Ops

### 7. TikTok Health
- **Purpose**: Ensure the TikTok ingestion pipeline is functioning by checking if any `TiktokVideo` records have been created in the last 24 hours. Alert if none.
- **Files**:
  - Source: `AI_Native_Lang/demo/tiktok_health.lang`
  - Copy: `AI_Native_Lang/examples/autonomous_ops/tiktok_health.lang`
  - Runner: `scripts/run_tiktok_health.py`
- **Cron**: Daily at 01:30 America/Chicago
- **Adapters**: `db.F` (query `TiktokVideo.created_at`), `memory.put`, `email.G`
- **Alert if**: No videos with `created_at` within last 24h
- **Memory record**:
  - Namespace: `"ops"`
  - Kind: `"monitor.tiktok_health"`
  - Payload: `{ "latest_video_age_hours": float, "videos_last_24h": int, "ts": now_iso }`
  - TTL: 90 days

---

## Pending (Adapter Gaps)

The following programs were planned but not implemented due to missing adapters:

- **SEO Freshness**: Needs filesystem adapter to check modification times of report files in `seo/reports/`. Workaround: modify `seo_sweep_runner_v4_prod.js` to write a `memory.put` timestamp; then AINL can read that.
- **Disk Usage Trend**: Needs system metrics adapter (disk space, inode usage).
- **Log Error Rate**: Needs file read adapter (or regex adapter) to scan logs for error patterns.
- **API Quota**: Could be implemented via `http` adapter; left as a placeholder due to response shape uncertainty.

---

## Implementation Notes

- All `.lang` files follow the same pattern:
  1. Query data via `R db.F "<Model>" -> results`.
  2. Filter/aggregate using `Filter`, `ForEach`, and `core` math.
  3. Compute derived metrics.
  4. `If` threshold exceeded → send alert via `R email G` (or `R queue Put`).
  5. Persist a summary record via `R memory.put "ops" "monitor.<name>"`.
- Runner scripts are based on `scripts/run_token_cost_tracker.py`. They:
  - Compile the AINL file with `AICodeCompiler`.
  - Add `engine.caps.add('core')`.
  - Send Telegram start/completion/error messages.
  - Write pre/post oversight JSON to `/tmp/`.
  - Exits 0 on success, non-zero on failure.
- Cron entries were added via `openclaw cron add` JSON with `delivery.mode="none"` to avoid duplicate Telegram messages (the runners send their own).
- All schedules are in `America/Chicago` timezone.

---

## Verification Steps

To manually test a monitor:
```bash
python3 scripts/run_<program>.py
```
Check `/tmp/<program>_pre_oversight.json` and `/tmp/<program>_post_oversight.json` for compile/runtime details. Telegram messages will arrive if alerts are triggered.

---

**Generated:** 2026-03-14 by Apollo (OpenClaw Assistant)