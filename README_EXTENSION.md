# AINL Extended: Adapters & Self-Monitoring

This directory contains the implementation of expanded LLM/tool adapters and a comprehensive self-monitoring system for AINL.

## Components

- `adapters/` – Unified LLM adapter base and implementations (OpenRouter, Ollama). Plus MCP and OpenClaw tool adapters.
- `intelligence/monitor/` – Metrics collector, cost tracker, health checks, budget policy, Telegram alerts, and a Flask dashboard.
- `docs/` – Adapter developer guide, monitoring operations, and integration notes for existing intelligence programs and external executor bridge.
- `tests/` – Conformance and unit tests.

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Ensure environment variables:
   - `OPENROUTER_API_KEY` (if using OpenRouter)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional alerts)
3. Run the dashboard: `python -m intelligence.monitor.dashboard.server`
   - View at http://localhost:8080
   - Metrics at http://localhost:8080/api/metrics
   - Health at http://localhost:8080/health/live and /health/ready

## Integrating with AINL Programs

At the beginning of each run, call `BudgetPolicy().check_and_enforce(run_id)`. After LLM calls, log usage via `CostTracker().add_cost(...)`. See `docs/INTELLIGENCE_PROGRAMS_INTEGRATION.md`.

## Testing

Run `pytest tests/` to ensure adapters and monitoring components work.

## Patch

The file `added.patch` contains a unified diff you can apply to the target AINL repository (e.g., `~/.openclaw/AI_Native_Lang/`):

```bash
cd ~/.openclaw/AI_Native_Lang/
git apply ~/.hermes/workspace/ainl/added.patch
```

If the target is not a git repo, you can copy the new files/directories manually.
