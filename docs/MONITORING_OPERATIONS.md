# Monitoring Operations for AINL

## Components

- **MetricsCollector**: in-memory histogram/counter metrics.
- **CostTracker**: SQLite DB (`~/.ainl/costs.db`) storing run costs and budget.
- **BudgetPolicy**: enforces monthly limits and alerts.
- **HealthStatus**: liveness/readiness probes.
- **Dashboard**: web UI at http://localhost:8080

## Setup

1. Ensure `intelligence/monitor` package is importable.
2. Run `python -m intelligence.monitor.dashboard.server` to start the dashboard.
3. Optionally configure Telegram alerts:
   ```bash
   export TELEGRAM_BOT_TOKEN=your_bot_token
   export TELEGRAM_CHAT_ID=your_chat_id
   ```
4. Set budget in `~/.ainl/costs.db` (table `budget`):
   ```sql
   INSERT INTO budget (monthly_limit_usd, alert_threshold_pct, throttle_threshold_pct) VALUES (20.0, 0.8, 0.95);
   ```

## Integrating with Workflows

At the start of any LLM call, call:

```python
from intelligence.monitor.budget_policy import BudgetPolicy
policy = BudgetPolicy()
result = policy.check_and_enforce(run_id)
if result == "throttled":
    # Reduce max_tokens or skip
    pass
```

After an LLM adapter returns `usage`, call:

```python
from intelligence.monitor.cost_tracker import CostTracker
ct = CostTracker()
ct.add_cost(run_id, provider, model, usage.prompt_tokens, usage.completion_tokens, adapter.estimate_cost(...))
```

## Metrics

Prometheus‑compatible exposition on `/api/metrics`. Key metrics:

- `ainl_workflow_runs_total`
- `ainl_workflow_success`
- `ainl_node_calls_total{node_type}`
- `ainl_llm_tokens_total{provider,model}`
- `ainl_llm_cost_total{provider,model}`
- `ainl_budget_spent_usd`
- `ainl_budget_usage_pct`

## Alerts

- **Telegram**: configured via env vars; sent when threshold exceeded or throttling.
- **Email**: stub for SMTP configuration.
- **Webhook**: generic POST to URL with payload.

## Troubleshooting

- DB locked? Use connection pooling or ensure single writer.
- High memory? MetricsCollector holds all metrics; consider TTL.
- Adapter down? Health check `ready` reflects adapter connectivity via custom logic.

## Automation

Add to existing `self_monitor.py`:
- Daily: reconcile costs with provider statements
- Hourly: check health endpoints and restart dashboard if dead
