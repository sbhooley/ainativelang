# LLM Adapter Usage Guide

This guide covers how to configure and use the expanded LLM adapter ecosystem in AINL, including fallback chains, JSON mode, and cost monitoring.

## Migrating from `llm_query`

The legacy **`llm_query`** runtime adapter remains available behind `--enable-adapter llm_query` or `AINL_ENABLE_LLM_QUERY=true`, but **instantiating it emits a `DeprecationWarning`**. Prefer the unified pipeline: register **`llm`** via `register_llm_adapters` and use **`R llm completion ...`** (or your graph’s equivalent) with `config.yaml` `llm:` / fallback chain as below. See `adapters/llm_runtime.py` and `adapters/__init__.py` for registration details.

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


Tell AINL to load this configuration:

- CLI flag: `--config path/to/config.yaml`
- Environment variable: `AINL_CONFIG=path/to/config.yaml`

As an alternative, you can enable specific adapters without a config file using:

- CLI flag: `--enable-adapter llm.openrouter` (repeatable)
- Environment variable: `AINL_ENABLED_ADAPTERS=llm.openrouter,llm.anthropic`

The `--config` approach is recommended for LLM setup because it also defines the fallback chain, circuit breaker settings, and provider-specific options.

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


## Monitoring & Alerting

The AINL ecosystem includes a lightweight monitoring stack:

- **Runtime metrics**: Adapters and circuit breakers emit metrics via `RuntimeObservability.emit`. These are:
  - Printed as JSON to stderr when `AINL_OBSERVABILITY=1`
  - Optionally written to a JSONL file via `AINL_OBSERVABILITY_JSONL=/path/metrics.jsonl`
  - Always forwarded to the in‑memory collector for Prometheus export

- **Prometheus endpoint**: Run `python scripts/serve_dashboard.py` and scrape `http://localhost:8080/api/metrics` for:
  - `circuit_breaker_state{provider="...",state="open|closed|half_open"}`
  - `cost_estimate_drift_total`, `cost_estimate_drift_pct{provider="...",model="..."}`

- **Health checks**:  
  `GET /health/live` returns `200 OK` if the process is alive.  
  `GET /health/ready` returns `200` when collector and cost DB are ready.

- **Cost validation service**: `services/cost_validator.py` runs in the background (if started) and compares adapter estimates against live provider prices (OpenRouter) every 6 hours by default. On drift >10%, it emits `cost_estimate_drift_total` and `cost_estimate_drift_pct`.

See `docs/AGENT_GUIDE_INDEX.md` for a full feature map.

## Using LLM Adapters with MCP (Hermes‑Agent / OpenClaw Skill)

When running the AINL MCP server (`scripts/ainl_mcp_server.py`), LLM adapters are **not** enabled by default to preserve a minimal attack surface. To enable them:

1. Set `AINL_CONFIG` to point to your YAML config file **or** set `AINL_MCP_LLM_ENABLED=1`.
2. Start the server: `python scripts/ainl_mcp_server.py`.
3. The server will:
   - Load the config (with env‑var expansion).
   - Call `register_llm_adapters()` to register the `llm` composite and the individual provider adapters.
   - Relax the `network` privilege tier restriction so LLM adapters can make outbound requests.
4. Connect your MCP client (Hermes‑Agent, OpenClaw skill) to the server as usual.

If `AINL_CONFIG` is set, the server automatically registers the LLM adapters defined under `llm.providers` and uses `llm.fallback_chain`. If `AINL_MCP_LLM_ENABLED=1` but no config is provided, the server will attempt to use default (no‑op) adapters; you should provide a config.

See `docs/AGENT_GUIDE_INDEX.md` for a complete agent‑oriented reference.

