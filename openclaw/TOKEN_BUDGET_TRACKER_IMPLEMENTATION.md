# Token Budget Tracker — Implementation Log

**Consultant:** Apollo  
**Date:** 2026-03-12  
**Goal:** Proactively manage LLM token spending by maintaining a rolling weekly budget, persisting usage to memory, and alerting when nearing limits.

---

## Program Overview

| Attribute | Value |
|-----------|-------|
| Source file | `examples/autonomous_ops/token_budget_tracker.lang` |
| Deployed to | `demo/token_budget_tracker.lang` |
| Schedule | Hourly, at minute 0 |
| Runner | `scripts/run_token_budget_tracker.py` |
| Cron job ID | `59994c49-be2e-404b-9914-1a7d8693e4d9` |
| Telegram channel | Last (main session) |
| Budget config | `long_term.budget_config` (record_id `weekly`) |

---

## How It Works

### Data sources
- OpenRouter usage API (`https://openrouter.ai/api/v1/usage`) — requires `OPENROUTER_API_KEY`
- Memory store (`workflow.token_cost_state`) — past 7 days of daily summaries
- Memory store (`long_term.budget_config`) — weekly budget in USD

### Workflow (hourly)
1. Load budget from `memory.get "long_term" "budget_config" "weekly"`; fallback to $10 default.
2. Fetch today’s usage from OpenRouter API via `http GET`.
3. Query memory for all `workflow.token_cost_state` records with `record_id` dating to the last 7 days via `memory.list(updated_since)`.
4. Sum stored costs + today’s cost → weekly total.
5. Compute pct_used = weekly_cost / budget.
6. Persist today’s summary to `workflow.token_cost_state` with 7‑day TTL.
7. If `pct_used > 0.9`, send an alert via `queue Put "notify"`; otherwise send a normal summary.
8. On HTTP failures, send an error notification.

### Payloads
Normal summary:

```json
{
  "module": "token_budget_tracker",
  "date": "2026-03-12",
  "week_cost_usd": 8.45,
  "week_tokens": 123456,
  "budget_usd": 10.0,
  "pct_used": 0.845,
  "status": "normal",
  "ts": "2026-03-12T18:00:00Z"
}
```

Alert (>90%):

```json
{
  "module": "token_budget_tracker",
  "date": "2026-03-12",
  "week_cost_usd": 9.20,
  "week_tokens": 135000,
  "budget_usd": 10.0,
  "pct_used": 0.92,
  "status": "budget_near_limit",
  "ts": "2026-03-12T18:00:00Z"
}
```

Error:

```json
{
  "module": "token_budget_tracker",
  "status": "http_error",
  "status_code": 503,
  "ts": "2026-03-12T18:00:00Z"
}
```

---

## Design Decisions

- **Rolling 7-day total** instead of calendar week aligns with “weekly” and handles arbitrary start dates.
- **Persist daily summaries** in `workflow.token_cost_state` so historical data survives restarts and allows audits.
- **TTL 7 days** automatically expires old entries; `memory.prune` can be run periodically for cleanup.
- **Budget stored in `long_term.budget_config`** makes it editable without code change (use `memory.put`).
- **Alert threshold fixed at 90%** for simplicity; can be parameterized in config later.
- **Used `ops.Env` for API key** — consistent with other AINL programs accessing secrets.

---

## Recreating This Monitor

1. **Write AINL** under `examples/autonomous_ops/token_budget_tracker.lang` using the same pattern (non‑strict mode).
2. **Copy to `demo/`** for deployment.
3. **Create runner script** (`scripts/run_token_budget_tracker.py`) following the common template:
   - Set `BASE = Path(__file__).resolve().parent.parent`
   - Add `'AI_Native_Lang'` to `sys.path`
   - Import compiler, engine, registry, oversight tools
   - Compile with `strict_mode=False`
   - Write `/tmp/<name>_pre_oversight.json`
   - Add `core` to engine caps
   - Run label 0
   - Capture runtime, token usage, and send Telegram messages
   - Write `/tmp/<name>_post_oversight.json`
4. **Make executable**: `chmod +x scripts/run_token_budget_tracker.py`
5. **Add cron job** via OpenClaw:

```bash
openclaw cron add \
  --name "Token Budget Tracker (AINL)" \
  --cron "0 * * * *" \
  --session isolated \
  --agent main \
  --message 'Execute the token budget tracker AINL program and report results.\n\n1) Run: python3 /Users/clawdbot/.openclaw/workspace/scripts/run_token_budget_tracker.py\n2) Capture stdout/stderr.\n3) In your final message, include:\n   - The exit status\n   - The output from the script\n   - Any errors\n\nIf the command fails, report the error and stop.'
```

6. **Set environment**:
   - `OPENROUTER_API_KEY` must be available to the runner (via shell environment or Gateway env).
   - Optionally `OPENCLAW_TARGET` to control Telegram destination.

7. **Initialize budget** (optional):

```bash
python -c "
from adapters.openclaw_integration import openclaw_monitor_registry
from runtime.engine import RuntimeEngine
reg = openclaw_monitor_registry()
engine = RuntimeEngine(None, adapters=reg, execution_mode='graph-preferred')
engine.caps.add('core')
engine.call('memory.put', ['long_term', 'budget_config', 'weekly', {'budget_usd': 10.0}], {})
"
```

---

## Benchmarks (initial)

- **Compile time**: ~1–2 seconds
- **Runtime**: depends on OpenRouter API latency; typically 10–15s
- **Token usage**: ~1k tokens per run (small)
- **Telegram messages**: 3 per run (start, compile OK, completion) + optional error alerts

*Note: These are placeholders; actual numbers will appear after the first few runs.*

---

## Status

- Created: 2026-03-12
- Deployed: Not yet (cron added; awaiting first run)
- Runner: `scripts/run_token_budget_tracker.py` implemented and executable
- Documentation: This file
- Consultant report: Appended to `AI_CONSULTANT_REPORT_APOLLO.md`

---

## Open Items

- Record actual runtime and token counts after first runs.
- Fine‑tune alert threshold if needed; could add `budget_warning_pct` in config.
- Consider adding a `memory.prune` cron to clean up old `workflow.token_cost_state` records (TTL helps but explicit prune is cleaner).
