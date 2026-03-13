# Standardized Health Envelope

**Date:** 2026-03-12  
**Author:** Apollo  

---

## Purpose

Provide a common payload shape for all autonomous ops monitors to simplify dashboarding, correlation, and downstream processing.

---

## Schema

All monitors send a `queue` message with this top‑level structure:

```json
{
  "envelope": {
    "version": "1.0",
    "generated_at": "2026-03-12T19:20:00Z"
  },
  "module": "<monitor_name>",
  "status": "ok" | "alert",
  "ts": "<ISO timestamp of measurement>",
  "metrics": { ... module‑specific key/value pairs ... },
  "history_24h": {
    "count": <number of breach/slow events in last 24h>,
    "...": "other aggregates as relevant"
  },
  "meta": {
    "runtime_seconds": <number>,
    "tokens": { "prompt": N, "completion": M, "total": K }
  }
}
```

- `metrics` contains the current snapshot values (e.g., `recent_count`, `video_fresh`, `phone_ok_pct`).
- `history_24h` provides short‑term trend context derived from `memory.list(updated_since=now-1d)`.
- `meta` allows runtime stats to be captured separately from business metrics.

---

## Migration

Monitors are updated one by one to produce this envelope. Downstream consumers (Telegram, dashboards) can tolerate the enhanced structure as they already parse unknown fields.

---

## Example (TikTok SLA)

```json
{
  "envelope": { "version": "1.0", "generated_at": "2026-03-12T19:15:57Z" },
  "module": "tiktok_sla",
  "status": "ok",
  "ts": "2026-03-12T19:15:00Z",
  "metrics": {
    "recent_count": 5,
    "video_fresh": true,
    "backup_fresh": true
  },
  "history_24h": {
    "breaches": 0
  },
  "meta": {
    "runtime_seconds": 18,
    "tokens": { "prompt": 33700, "completion": 1000, "total": 34700 }
  }
}
```

---

## Notes

- `status` is derived: if `breach` or `any_breach` true → `"alert"`, else `"ok"`.
- `metrics` may include computed ratios (e.g., `phone_ok_pct`) as needed.
- `history_24h` may include multiple fields (`slow_targets`, `breach_reasons`) depending on monitor.
