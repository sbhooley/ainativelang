# Externalized Configuration for Autonomous Ops

**Date:** 2026-03-12  
**Owner:** Apollo  

---

## Rationale

Hard‑coding thresholds, TTLs, and paths in AINL programs makes tuning risky (code edits) and impossible to adjust at runtime. We move all tunable values to `memory` under the `config` namespace.

---

## Schema

Each monitor has a config record: `config.<module>`, e.g. `config.canary_sampler`. Payload is an object with keys:

- `threshold_ms` (for canary targets, if applicable)
- `breach_cooldown_seconds` (alert suppression window)
- `history_ttl_seconds` (TTL for memory‑persisted events)
- `summary_include_*` (booleans to control payload fields)
- `sources` (array of endpoints for Canary)
- `sla_hours` (for TikTok: max age in hours)
- `backup_dir` (path)
- … module‑specific fields

Default configs are provisioned by a bootstrap script or manually via `memory.put`. Monitors read with `R memory F "config" "<module>" ->cfg` and fall back to hard‑coded defaults if missing.

---

## Implementation Steps

1. Create `scripts/bootstrap_autonomous_ops_config.py` to write default configs to memory.
2. Update each monitor to:
   - `R memory F "config" "<module>" ->cfg` at startup
   - Replace constants with `cfg.<field>` (using `or` to fallback)
   - Keep backward compatibility: if config missing, use original defaults
3. Optionally add an admin AINL program to update configs via `memory.P`.

---

## Benefits

- Tune thresholds without redeploying code
- A/B test different settings by updating config only
- Central documentation of all operational knobs

---

## Next

Add config update endpoints or a simple CLI script to adjust values on the fly.
