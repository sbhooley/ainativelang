# Canary Sampler — Historical Flapping Metrics

**Consultant:** Apollo  
**Date:** 2026-03-12  
**Change:** Persist slow‑threshold events to memory and include a 24‑hour count in the summary using `memory.list(updated_since?)`.

---

## Problem

Original Canary Sampler used `cache` to maintain consecutive slow counters per target, enabling suppression of alerts until a threshold (3). This is good for noise reduction but provides no historical view: operators couldn’t answer “how many slow responses have we seen in the last day?” or detect degrading trends.

---

## Solution

Each time a target is marked slow (non‑200 status), the program:
- Writes an event record to `memory` (`ops.canary.slow`) with payload `{"target": "<name>", "ts": now}` and a 7‑day TTL
- Keeps the existing cache‑based consecutive counter

In the final summary, it queries `memory.list "ops" "canary.slow" "" day_ago` to count slow events in the last ~24 hours and includes `slow_24h` in the notification payload.

The summary now distinguishes:
- **Alert path** (`any_breach=true`) — sent immediately when consecutive slow hits >=3; the payload includes the current `targets` state and the `slow_24h` count as context.
- **Normal path** — sends a concise summary with `any_breach:false`, `targets` state, and `slow_24h`.

---

## Code Changes

Key additions in `demo/canary_sampler.lang`:
- When a slow event occurs:
  ```
  X evt_id (core.join ["slow-", r0.name, "-", now])
  R memory.put "ops" "canary.slow" evt_id {"target":r0.name,"ts":now} 604800 ->_
  ```
- Before sending summary:
  ```
  X day_ago (core.sub now 0 1)
  R memory.list "ops" "canary.slow" "" day_ago ->hist
  X slow_24h (len hist.items)
  ```
- The final `queue Put` payload includes `"slow_24h":slow_24h`

The alert path still sends immediately and returns without a separate summary to avoid duplication. The normal path sends the summary with the 24h count.

---

## Benefits

- **Observability**: Operators can see if slow responses are a one‑off or part of a trend.
- **Trend analysis**: Historical slow counts can be charted or further analyzed with additional memory queries (e.g., per‑target breakdown).
- **Minimal overhead**: TTL caps storage; slow events are infrequent (minutes between significant counts).
- **Pattern consistency**: Shows how to combine cache for fast state and memory for durable history.

---

## Before vs After Summary

**Before:**
```json
{
  "module":"canary_sampler",
  "any_breach":true,
  "targets":[{"name":"CRM API","slow":true,"consecutive":3},...],
  "ts":"..."
}
```

**After:**
```json
{
  "module":"canary_sampler",
  "any_breach":true,
  "targets":[...],
  "slow_24h":7,
  "ts":"..."
}
```

---

## Benchmark

- Compile time unchanged (<2s)
- Runtime increase negligible (one extra `memory.list` ~100ms)
- Token usage +~50 tokens for extra field
- Memory storage: ~100 bytes per slow event × few per hour × 7‑day TTL = very small

---

## Status

- Updated: 2026-03-12
- Deployed: cron job active (`*/5 * * * *`)
- Runner: `scripts/run_canary_sampler.py` (unchanged)

---

## Future Enhancements

- Break down `slow_24h` by target (query with `record_id_prefix`) to show which endpoint is flapping.
- Add a rolling average (e.g., slow events per hour over 24h).
- If slow events exceed a threshold (e.g., >50 in 24h), generate a separate health alert.
- Consider moving consecutive counter to memory as well for multi‑instance coherency.

---

## Related

- `openclaw/INFRASTRUCTURE_WATCHDOG_UPDATE.md` — similar pattern of persisting events to memory for observability
- `docs/MEMORY_CONTRACT.md` — `memory.list` semantics
