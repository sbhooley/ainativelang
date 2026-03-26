# AINL Auto-Tuner — Complete Documentation

## Overview

The `auto_tune_ainl_caps` program automatically adjusts AINL-related environment variables in OpenClaw to maintain token savings in the 90–95% range. It is production-grade, safe, and designed for any OpenClaw+AINL deployment.

## How It Works

1. **Data Collection**  
   Reads `MONITOR_CACHE_JSON` (workflow → token_budget) to compute actual daily savings vs. estimated baseline.

2. **Bridge Analysis**  
   Queries the AINL SQLite bridge DB (`ainl_memory.sqlite3`) for recent report sizes to determine if `AINL_BRIDGE_REPORT_MAX_CHARS` is too loose or too tight.

3. **Promoter Analysis**  
   Infers promoter cap adequacy from savings trends:  
   - Savings below target → tighten `PROMOTER_LLM_MAX_PROMPT_CHARS` and `PROMOTER_LLM_MAX_COMPLETION_TOKENS`  
   - Savings above target → relax slightly (avoid over-truncation)

4. **Stability Guard**  
   Requires at least 7 days of history and 5 consecutive days within target range before making adjustments. Changes are limited to ~10–15% per week.

5. **Output**  
   Writes recommendations to `$WORKSPACE/.ainl/tuning_recommendations.json` and, if `OPENCLAW_AINL_AUTO_APPLY=true`, applies them via OpenClaw `config.patch`.

## Files

- `intelligence/auto_tune_ainl_caps.lang` — main AINL program
- `scripts/run_auto_tune_ainl_caps.sh` — runner script (calls `run_intelligence.py`)
- Optional cron job template (see below)

## Setup

### 1. Ensure AINL integration is complete

Follow `docs/AINL_INTEGRATION_GOLDEN.md` first. The auto-tuner depends on:
- Pinned workspace env vars
- `session_context.md` bootstrap preference
- Weekly bridge job (produces SQLite history)
- `MONITOR_CACHE_JSON` being populated

### 2. Add cron job (weekly)

Run after the weekly token trends job (e.g., Sunday 11 AM):

```bash
openclaw cron add '{
  "name": "AINL Auto-Tune Caps",
  "schedule": { "kind": "cron", "expr": "0 11 * * 0" },
  "payload": {
    "kind": "agentTurn",
    "agentId": "ainl-advocate",
    "message": "run intelligence: auto_tune_ainl_caps"
  },
  "delivery": { "mode": "announce" },
  "sessionTarget": "isolated",
  "enabled": true
}'
```

### 3. Choose mode

**Dry-run (default):** The tuner only writes recommendations; you review and apply manually.

**Auto-apply:** Set environment variable in OpenClaw config:

```bash
openclaw gateway config.patch '{
  "env": { "vars": { "OPENCLAW_AINL_AUTO_APPLY": "true" } }
}'
```

Use auto-apply only after verifying dry-run output looks sane for a few weeks.

## Configuration Tuning

The program has built-in defaults (see `config` block in the `.lang` file). You can override them by setting environment variables before running:

- `AINL_TUNER_MIN_HISTORY_DAYS` (default 7)
- `AINL_TUNER_TARGET_SAVINGS_MIN` (default 90.0)
- `AINL_TUNER_TARGET_SAVINGS_MAX` (default 95.0)
- `AINL_TUNER_STABLE_DAYS_REQUIRED` (default 5)
- `AINL_TUNER_BRIDGE_STEP_FACTOR` (default 0.85)
- `AINL_TUNER_PROMOTER_STEP_FACTOR` (default 0.90)
- `AINL_TUNER_AUTO_APPLY` (default false)

Example: `OPENCLAW_AINL_AUTO_APPLY=true AINL_TUNER_TARGET_SAVINGS_MIN=92.0 ./scripts/run_auto_tune_ainl_caps.sh`

## Outputs

- `$WORKSPACE/.ainl/tuning_recommendations.json` — latest recommendation (human-readable)
- `$WORKSPACE/.ainl/tuning_log.json` — history of all runs and applied changes

### Recommendation JSON schema

```json
{
  "generated_at": "2026-03-25T19:30:00Z",
  "savings_pct": 91.2,
  "history": [88.1, 89.4, 90.1, 91.0, 91.2, ...],
  "current": {
    "bridge_chars": 3132,
    "promoter_prompt": 4000,
    "promoter_completion": 1000
  },
  "recommended": {
    "bridge_chars": 2500,
    "promoter_prompt": 3600,
    "promoter_completion": 900
  },
  "bridge_sizes_sample": [2100, 1950, 2300, ...],
  "auto_apply": false,
  "applied": false,
  "reason": "Stable savings for 5 days; bridge size indicates overprovision"
}
```

## Safety & Limits

- **Step size caps:** Changes are limited to 10–20% per run to avoid sudden breakage.
- **Hard bounds:** Bridge chars between 500–5000; promoter prompt 1k–10k; completion 200–2k.
- **Stability requirement:** Will not tighten if 5 consecutive days within target hasn't been achieved.
- **Revertibility:** All changes go through OpenClaw config history; you can revert via `config.patch` or restore previous `openclaw.json`.
- **No destructive actions:** The tuner only edits `env.vars`; it does not modify code or cron schedules.

## Troubleshooting

- **No savings computed:** Check that `MONITOR_CACHE_JSON` contains `workflow.token_budget.baseline_estimated_total_tokens` and `actual_daily_total`. These are written by the AINL bridge and intelligence programs.
- **Bridge sizes empty:** Ensure `weekly-token-trends` cron is running and writing to SQLite. The table `bridge_reports` must exist.
- **Caps not changing:** The logic may decide no change is needed; this is normal if you're already within target with stable history.
- **Auto-apply not working:** Verify `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` and other env vars are set; the gateway user must have permission to `config.patch`.

## Advanced: Custom Hooks

You can extend the tuner by adding custom checks:

- Promoter truncation detection: parse promoter logs for "truncated" warnings.
- Quality signals: use agent satisfaction ratings if available.
- Multi-agent tuning: per-agent caps could be tuned by analyzing individual agent usage.

## Integration Checklist

- [ ] AINL integration golden steps completed
- [ ] `session_context.md` generation verified
- [ ] `MONITOR_CACHE_JSON` has at least 7 days of data
- [ ] Bridge SQLite contains report payloads (`bridge_reports` table)
- [ ] OpenClaw `env.vars` include all pinned paths and `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true`
- [ ] Dry-run of tuner completes without errors: `scripts/run_auto_tune_ainl_caps.sh`
- [ ] Review first `tuning_recommendations.json`
- [ ] (Optional) Enable auto-apply after confirming safe

## Maintenance

- Run `openclaw doctor --non-interactive` periodically to verify environment.
- Monitor `tuning_log.json` for applied changes and savings trends.
- If you manually adjust caps outside the tuner, consider resetting the tuner’s history or allowing it to re-stabilize.

## License

Same as AINL core (MIT). Feel free to copy into your own OpenClaw+AINL deployments.
