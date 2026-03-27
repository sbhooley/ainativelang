# LLM Adapter Usage Guide

This guide covers how to configure and use the expanded LLM adapter ecosystem in AINL, including fallback chains, JSON mode, and cost monitoring.

## Configuration

Create a `config.yaml` in your project root:

```yaml
llm:
  default_provider: openrouter
  fallback_chain: [openrouter, anthropic, ollama]
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_s: 300
  providers:
    openrouter:
      api_key: ${OPENROUTER_API_KEY}
      base_url: https://openrouter.ai/api/v1
      json_mode: true
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      json_mode: true
    ollama:
      base_url: http://localhost:11434
      json_mode: false
```

Environment variables are expanded automatically (e.g., `${OPENROUTER_API_KEY}`).

## Bootstrap Integration

In your application startup code (CLI or server):

```python
from runtime.adapters.base import AdapterRegistry
from adapters import register_llm_adapters
import yaml

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

runtime_reg = AdapterRegistry(allowed=["core", "llm", ...])
register_llm_adapters(runtime_reg, cfg)

# Then pass runtime_reg to RuntimeEngine
```

The `register_llm_adapters` helper constructs a fallback chain from the config and registers a runtime adapter named `llm` (and optionally individual provider adapters).

## Graph Usage

AINL graphs can now use the `llm` adapter for text completion:

```
R adapter=llm target=completion args=["Translate to French: Hello", 100] out=translated
```

To force a specific provider, you can either:

- Use `adapter=openrouter` if you registered each provider individually.
- Or adjust `fallback_chain` order to prioritize one provider.

### JSON Mode

When `json_mode: true` is set for a provider in the config, the adapter requests JSON-formatted responses (where supported). For example, to extract structured data:

```
R adapter=llm target=completion args=[
  "Extract name and age from: John is 30 years old.",
  50
] out=json_str
X fn=json_parse args=[json_str] out=data
```

The `json_parse` core function parses the string into a dictionary.

## Cost Estimation & Validation

Each adapter estimates cost based on token usage and built‑in pricing tables. The `CostValidator` service periodically fetches live prices (OpenRouter) and compares them to the estimates. If the drift exceeds 10%, it:

- Logs a warning.
- Increments Prometheus counter `cost_estimate_drift_total{provider, model}`.
- Sets gauge `cost_estimate_drift_pct{provider, model}`.

To enable cost validation, ensure `OPENROUTER_API_KEY` is set and optionally `COST_VALIDATOR_INTERVAL_HOURS` (default 6). The validator starts automatically on first use.

## Integration with OpenClaw Token‑Budget Alerts

The AINL adapters report token usage to the existing OpenClaw cost tracking system by calling `CostTracker.add_cost(...)` (if available in your environment). This integrates with the token‑budget alerts you already have configured (Telegram, email). Ensure the `intelligence/monitor/cost_tracker.py` module is importable and the database path `~/.ainl/costs.db` is writable.

If you wish to manually connect:

```python
from intelligence.monitor.cost_tracker import CostTracker

 tracker = CostTracker()
 tracker.add_cost(
     run_id=run_id,
     provider="anthropic",
     model="claude-3-5-sonnet-20241022",
     prompt_tokens=usage.prompt_tokens,
     completion_tokens=usage.completion_tokens,
     cost_usd=adapter.estimate_cost(usage.prompt_tokens, usage.completion_tokens)
 )
```

The `BudgetPolicy` can then enforce thresholds.

## Observability

Circuit breaker state is emitted as a gauge: `circuit_breaker_state{provider,state="closed|open|half_open"}` via `runtime/observability.py`. You can scrape these with Prometheus or view them in the dashboard (if running the monitoring stack).

## Security Notes

- LLM adapters are considered `network_facing` and may be restricted in sandboxed execution.
- API keys must come from environment or config; never hardcoded.
- When running untrusted graphs, ensure the adapter’s privilege tier aligns with your security policy.

## Troubleshooting

- **No LLM calls succeed**: check API keys and network connectivity; the circuit breaker may be open. Inspect logs for `CircuitOpenError`.
- **Cost drift warnings**: review your adapter’s `MODEL_PRICING` constants; OpenRouter prices may have changed. Consider updating your config to use a different model or adjust expected costs.
- **JSON mode not working**: not all providers support JSON mode; ensure `json_mode: true` is set and the model is capable (e.g., GPT‑4, Claude). If the response is not JSON, check provider documentation and adapter version.

## Future Extensions

- Tool use passthrough for Anthropic/Cohere (out of scope for Phase 1).
- Optional SDK‑based adapters via `ainativelang[anthropic]`.
