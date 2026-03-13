# Meta Monitor — Implementation

**Consultant:** Apollo  
**Date:** 2026-03-12  
**Category:** Autonomous Ops Extension

---

## Purpose

Monitor the health and timeliness of the autonomous monitors themselves. Detects if any monitor has not run successfully within its expected interval, based on heartbeats stored in `cache`.

---

## Program File

`demo/meta_monitor.lang` (source: `examples/autonomous_ops/meta_monitor.lang`)

---

## Schedule

Every 15 minutes.

---

## How It Works

- Reads an optional configuration from `memory` record `config.meta_monitor`. If absent, uses a default list of modules with their expected intervals (seconds).
- For each module:
  - Reads `cache` key `monitor_heartbeat.<module>` for last run timestamp.
  - Computes age: `now - last_ts` (or `-1` if missing).
  - Marks as stale if age > `interval_seconds * 2` OR missing.
- Collects list of stale modules; sends a summary envelope:
  - `status` is `"alert"` if any stale, else `"ok"`.
  - `metrics` includes `monitors_ok`, `monitors_stale`, and `stale_details` (array of `{name, age, interval}`).
- Writes its own heartbeat `monitor_heartbeat.meta_monitor`.

---

## Configuration

Optional `config.meta_monitor` memory record (JSON) can override the default modules and intervals:

```json
{
  "modules": [
    {"name":"infrastructure_watchdog","interval_seconds":300},
    {"name":"tiktok_sla_monitor","interval_seconds":900},
    ...
  ]
}
```

---

## Payload Example (OK)

```json
{
  "envelope": {"version":"1.0","generated_at":"2026-03-12T19:15:00Z"},
  "module":"meta_monitor",
  "status":"ok",
  "ts":"2026-03-12T19:15:00Z",
  "metrics":{
    "monitors_ok": 9,
    "monitors_stale": 0,
    "stale_details": []
  },
  "history_24h":{},
  "meta":{}
}
```

**Alert Example:**

```json
{
  "envelope": {"version":"1.0","generated_at":"2026-03-12T19:15:00Z"},
  "module":"meta_monitor",
  "status":"alert",
  "ts":"2026-03-12T19:15:00Z",
  "metrics":{
    "monitors_ok": 7,
    "monitors_stale": 2,
    "stale_details":[
      {"name":"canary_sampler","age":695,"interval":300},
      {"name":"lead_quality_audit","age":90000,"interval":86400}
    ]
  },
  "history_24h":{},
  "meta":{}
}
```

---

## Heartbeat Convention

All monitors under the autonomous ops pack must write `cache.set "monitor_heartbeat" "<module>" now` immediately before exiting successfully. This allows meta_monitor to track liveness.

---

## Verification

- Stop one monitor’s cron or block its execution.
- Wait >2× its interval.
- Run meta_monitor manually (`python3 scripts/run_meta_monitor.py`) or wait for cron.
- Expect Telegram alert listing the stale module(s).

---

## Notes

- The monitor does not attempt self‑healing (e.g., restart cron). That remains an operator task or separate remediation monitor.
- Heartbeats are written even if the monitor sent an alert; only failure/exception prevents the heartbeat.
- Intervals are approximate; cron drift is tolerated but 2× threshold provides cushion.

---

**Status:** Deployed 2026-03-12, operational.
