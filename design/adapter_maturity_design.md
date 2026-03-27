# Design Pass: Adapter Maturity & Ecosystem Expansion

**Repository:** `~/.openclaw/workspace/AI_Native_Lang/`  
**Date:** 2026-03-27  
**Author:** Hermes Agent  

## 1. Goals

- Add direct **Anthropic** and **Cohere** LLM adapters (alongside OpenRouter and Ollama).
- Implement **provider fallback chain** with **circuit breaker** for resilience.
- Achieve **>95% test coverage** for all adapter code, including latency and error injection.
- Add **cost estimation validation** – periodically fetch live pricing and compare to estimates; alert on significant drift.
- Integrate seamlessly with runtime via **LLMRuntimeAdapter** bridge.
- Hook metrics into existing **observability** and **audit logging**.
- Respect **security profiles** and privilege tiers for adapters.

## 2. Current State & Gaps

### Existing

- **LLM adapters** under `adapters/llm/`:
  - `openrouter.py` – uses OpenRouter API endpoint; supports JSON via `response_format`.
  - `ollama.py` – local Ollama.
  - Both implement `AbstractLLMAdapter` with `complete()` method.
- **Adapter registry** in `adapters/registry.py`:
  - `AdapterRegistry` with `register_llm`, `get_llm_adapter`, `list_providers`.
  - Auto-registers OpenRouter and Ollama on import.
- **Runtime engine** in `runtime/engine.py`:
  - Uses `RuntimeAdapter` interface.
  - Steps of type `R` call `self.adapters.call(adapter_name, target, args, context)`.
- **Existing `LlmQueryAdapter`** in `adapters/llm_query.py` provides a generic HTTP bridge to an LLM service, but is separate from the new `AbstractLLMAdapter` family.
- **Observability** infrastructure in `runtime/observability.py` (metrics, traces).
- **No tests** for adapters yet.
- **No fallback or circuit breaker** logic.

### Gaps

1. **Runtime Integration:** `AbstractLLMAdapter` implementations are *not* `RuntimeAdapter`s, so they cannot be used directly in `R` steps.
2. **Missing Providers:** Anthropic and Cohere are not available as direct adapters.
3. **Resilience:** No automatic failover or protection from flaky providers.
4. **Test Coverage:** Zero.
5. **Cost Tracking:** No in-repo validation against live provider pricing.
6. **Configuration:** No unified YAML/config for fallback chains and circuit breaker parameters.

## 3. Proposed Architecture

```
AINL Graph (R step: adapter="openrouter", target="completion", args=[...])
   |
   v
RuntimeEngine.adapters.call("openrouter", ...)
   |
   v
LLMRuntimeAdapter (new RuntimeAdapter wrapper)
   |
   v
FallbackLLMAdapter (optional, wraps multiple AbstractLLMAdapters in priority order)
   |
   v
CircuitBreaker (per-provider health)
   |
   v
Concrete provider adapter (OpenRouterAdapter, AnthropicAdapter, CohereAdapter, OllamaAdapter)
   |
   v
HTTP (or local) -> LLM response -> LLMResponse(content, usage, model)
```

### New Components

1. **`adapters/llm_runtime.py`** – `LLMRuntimeAdapter(RuntimeAdapter)`  
   Bridges the runtime's generic call to the `AbstractLLMAdapter` world.
   - `__init__(self, provider: str, config: dict | None = None)`
   - `call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any`:  
     - `target` is the method name (e.g., "completion"); calls `adapter.complete(...)`.  
     - `args` expected: `[prompt, max_tokens?]`.  
     - Returns dict: `{"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}}`.
   - Uses `LLMAdapterRegistry` to obtain the underlying adapter instance (cached per provider+config).
   - Respects security profiles: adapter is tagged `network_facing` and enforces config privilege checks (no hardcoded keys).

2. **`adapters/fallback.py`**
   - `CircuitBreaker`:
     - States: CLOSED, OPEN, HALF_OPEN.
     - Configurable `failure_threshold` (N consecutive errors) and `recovery_timeout_s`.
     - On error in CLOSED: increment counter; if >= threshold, transition to OPEN and record `opened_until` timestamp. Emit metric `circuit_breaker_state{provider,state="open"}`.
     - In OPEN: short‑circuit calls, raise `CircuitOpenError`. Metric `circuit_breaker_state{provider,state="open"}`.
     - HALF_OPEN: allow one trial call; success->CLOSED; failure->OPEN.
   - `FallbackLLMAdapter(AbstractLLMAdapter)`:
     - Constructor: `FallbackLLMAdapter(adapters: List[AbstractLLMAdapter])`.
     - `complete(...)` iterates through adapters; returns on first success; aggregates errors.
     - Each wrapped adapter has its own `CircuitBreaker` shared instance (so health is per-provider, not per‑request).
   - Helper `create_fallback_from_config(config: dict) -> AbstractLLMAdapter`:
     - Reads `llm.fallback_chain` (list of provider names) and `llm.circuit_breaker` settings from config (YAML/env).
     - Builds individual `AbstractLLMAdapter` instances via `LLMAdapterRegistry`, wraps each with its `CircuitBreaker`, then returns a `FallbackLLMAdapter` over them.
   - The runtime integration will call `create_fallback_from_config()` during engine bootstrap.

3. **`adapters/llm/anthropic.py`** – `AnthropicAdapter(AbstractLLMAdapter)`
   - Endpoint: `https://api.anthropic.com/v1/messages`
   - Auth: `X-API-Key` header from `config["api_key"]` (or env `ANTHROPIC_API_KEY`). Never hardcoded.
   - Models: `MODEL_PRICING` dict (e.g., `"claude-3-5-sonnet-20241022": {" prompt_price": 3.0, "completion_price": 15.0}`) in USD per 1M tokens.
   - JSON mode: include `"response_format": {"type": "json_object"}` if `config.get("json_mode", False)`.
   - Request body: `{"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}], ...}`.
   - Response: `content[0].text`, usage from `usage` field.
   - `estimate_cost(prompt_toks, completion_toks)` uses `MODEL_PRICING[model]`.
   - Error handling: map HTTP status codes to `AdapterError`; 429 triggers retry/backoff.
   - **Security:** tagged `network_facing`; respects privilege tier if used in sandboxed execution.

4. **`adapters/llm/cohere.py`** – `CohereAdapter(AbstractLLMAdapter)`
   - Endpoint: `https://api.cohere.ai/v1/generate`
   - Auth: `Authorization: Bearer ***` (env `COHERE_API_KEY`).
   - Models: e.g., `command-r-plus`, `command-r` with pricing per 1K tokens (input/output) stored in `MODEL_PRICING`.
   - JSON mode: `"format": "json"` in request.
   - Request: `{"model": model, "prompt": prompt, "max_tokens": max_tokens, ...}`.
   - Response: `generations[0].text`, usage from `meta.billed_units`.
   - Same cost estimation pattern.

5. **`services/cost_validator.py`**
   - `CostValidator`:
     - Sources:  
       - OpenRouter: `GET https://openrouter.ai/api/v1/models` – cached 24h. Requires `OPENROUTER_API_KEY`.
       - Anthropic/Cohere: use static `MODEL_PRICING` from their respective adapters; optional manual update. No live fetch in Phase 1.
     - `validate()`: for each known provider+model, get live price, compare with adapter's `estimate_cost`. If absolute difference > 10%, log warning and emit metrics:
       - Increment counter `cost_estimate_drift_total{provider, model}`
       - Set gauge `cost_estimate_drift_pct{provider, model}` with percentage difference.
   - Run periodically: background thread started on first use, interval configurable via `COST_VALIDATOR_INTERVAL_HOURS` (default 6).
   - **Observability Integration:** Directly uses `runtime/observability.py` if available; otherwise falls back to `logging` and optional `prometheus-client`.

6. **`tests/`** – new test files:
   - `tests/conftest.py` with fixtures (mock HTTP using `responses`).
   - `tests/test_anthropic.py`, `tests/test_cohere.py`
   - `tests/test_fallback.py`
   - `tests/test_circuit_breaker.py`
   - `tests/test_cost_validator.py`

7. **`adapters/__init__.py`** – extend to:
   - Import new modules for side‑effects (registry auto‑registration of Anthropic/Cohere).
   - Expose helper `register_llm_adapters(registry: AdapterRegistry, config: dict)` that:
     - Builds fallback chain via `create_fallback_from_config(config)`.
     - Registers a single runtime adapter named `"llm"` that points to the fallback. Alternatively, register each provider individually based on `fallback_chain` order. We'll decide: likely register each provider separately for runtime, and a composite `"llm"` for convenience.
   - This keeps changes to core runtime to zero; the application simply imports `adapters` and calls the helper during bootstrap.

## 4. Runtime Integration

We will implement the **LLMRuntimeAdapter** bridge so existing `AbstractLLMAdapter`s become usable as runtime adapters.

**Bootstrap sequence** (in the application entrypoint, e.g., `ainl` CLI or server):

```python
from runtime.adapters.base import AdapterRegistry as RuntimeAdapterRegistry
from adapters import register_llm_adapters
import yaml

# Load config: e.g., config.yaml or environment
with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

runtime_reg = RuntimeAdapterRegistry(allowed=["core", "llm", ...])  # allow llm
register_llm_adapters(runtime_reg, cfg)

engine = RuntimeEngine(ir=ir, adapters=runtime_reg, ...)
```

Inside `register_llm_adapters`:

- For each provider in `cfg["llm"]["fallback_chain"]`, create an `AbstractLLMAdapter` via `LLMAdapterRegistry.get_llm_adapter(provider, provider_config)`.
- Wrap each with a `CircuitBreaker` (shared per provider).
- Build a `FallbackLLMAdapter` over them in order.
- Register a **runtime adapter** under the name `"llm"` (or each provider name) that delegates to the fallback:
  ```python
  runtime_reg.register("llm", LLMRuntimeAdapter(fallback_adapter))
  ```
  or register each provider separately if we want fine‑grained control.

**Graph usage**:

AINL graph `R` step can then specify:
```
R adapter=llm target=completion args=["prompt here", 500] out=result
```
or if we register per‑provider, `adapter=openrouter`, etc.

### Observability Hooks

- **Circuit breaker state**: emit gauge `circuit_breaker_state{provider,state="closed|open|half_open"}`
- **Cost drift**: `cost_estimate_drift_total` and `cost_estimate_drift_pct`
- These use `runtime/observability.py` methods (`observability.emit(...)`). If observability is not enabled, they noop.

### Security & Privilege

- LLM adapters are marked `network_facing=True`.
- They obtain API keys from environment or config validated at initialization.
- No hardcoded credentials.
- Adapters should respect any runtime security profile (e.g., disallowed env vars) through the existing `sandbox_metadata_provider` if applicable. We'll document best practices.

## 5. Testing Strategy

- Use `pytest` with `responses` to mock HTTP calls for Anthropic/Cohere.
- Fixtures: sample successful responses and error payloads.
- Test categories:
  - **Adapters**: basic completion, JSON mode, 429 retry with backoff, invalid API key, malformed response.
  - **Fallback**: primary fails, backup returns; all fail raises combined error.
  - **CircuitBreaker**: opens after threshold, recovers after timeout, HALF_OPEN trial.
  - **CostValidator**: drift detection triggers metrics and logs.
- Coverage enforced via `pytest-cov` – fail if <95%.

## 6. Configuration Example

`config.yaml`:
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

The `register_llm_adapters` helper reads this config and constructs the composite runtime adapter.

## 7. Dependencies

**Production:**
```
httpx>=0.27.0        # HTTP client (async capable)
```

**Optional extras** (not required for minimal install):
```
ainativelang[anthropic]  # installs anthropic>=0.25.0
ainativelang[cohere]     # installs cohere>=5.3.0
```

**Testing:**
```
responses>=0.23.0
pytest>=7.0
pytest-cov>=4.0
```

We will write adapters using `httpx` by default to keep the core lightweight. If users prefer the official SDKs, they can install the extras and we'll add optional code paths (Phase 2). Phase 1 focuses on direct HTTP.

## 8. Step‑by‑step Implementation Plan

| Step | Task | Estimated Effort |
|------|------|------------------|
| 1 | Implement `LLMRuntimeAdapter` bridge; integrate with one existing provider (OpenRouter) to prove runtime path | 0.5 day |
| 2 | Add configuration loader (YAML) and `register_llm_adapters` helper | 0.5 day |
| 3 | Implement `CircuitBreaker` and `FallbackLLMAdapter` | 0.75 day |
| 4 | Register fallback chain from config (multiple providers) | 0.25 day |
| 5 | Implement `AnthropicAdapter` (direct HTTP) with JSON mode | 0.5 day |
| 6 | Implement `CohereAdapter` (direct HTTP) | 0.5 day |
| 7 | Unit tests for Anthropic and Cohere adapters | 0.5 day |
| 8 | Tests for fallback and circuit breaker | 0.5 day |
| 9 | Implement `CostValidator` with OpenRouter price fetch (caching) | 0.75 day |
|10 | Tests for `CostValidator` | 0.25 day |
|11 | Observability integration (breaker state, cost drift metrics) | 0.25 day |
|12 | Documentation (`docs/LLM_ADAPTER_USAGE.md`) with examples, config, cost validation notes, and integration with token‑budget alerts | 0.25 day |
|13 | Final coverage sweep and adjustments | 0.25 day |
| | **Total** | **~5.5 days** |

## 9. Risks & Mitigations

- **API rate limits**: 429 handling with exponential backoff; circuit breaker prevents cascading failures.
- **Pricing source instability**: Use caching and tolerate failures (skip validation if fetch fails).
- **Dependency bloat**: Stick to `httpx` for HTTP; keep SDKs optional extras.
- **Test flakiness**: Deterministic mock data, avoid real network in unit tests.
- **Security**: Ensure API keys are sourced from env/config and never logged; adapters respect sandbox restrictions.

## 10. Success Criteria

- All new adapters and support classes have unit tests (>95% line coverage).
- AINL graph can perform `R adapter=llm target=completion` with fallback chain active; primary failure automatically uses backup.
- Circuit breaker opens after threshold and recovers after timeout; state visible via metrics.
- Cost validator detects artificial price drift and emits metrics/logs.
- Graph example using Anthropic adapter with JSON mode returns valid JSON in <5 s.
- Documentation includes configuration, example graph, cost estimation accuracy notes, and integration with existing OpenClaw token‑budget alerts.
- No changes required to `runtime/engine.py`; integration via bootstrap only.

## 11. Appendix – File Manifesto

**New files to create:**
- `adapters/llm/anthropic.py`
- `adapters/llm/cohere.py`
- `adapters/llm_runtime.py`
- `adapters/fallback.py`
- `services/cost_validator.py`
- `tests/conftest.py`
- `tests/test_anthropic.py`
- `tests/test_cohere.py`
- `tests/test_fallback.py`
- `tests/test_circuit_breaker.py`
- `tests/test_cost_validator.py`
- `docs/LLM_ADAPTER_USAGE.md`

**Modified files:**
- `adapters/__init__.py` – import new modules and expose `register_llm_adapters(registry, config)`.
- `requirements.txt` – add `httpx`; optional extras `[anthropic]`, `[cohere]`.
- (Optional) `config.yaml.example` to illustrate setup.

**Design docs:**
- This document: `design/adapter_maturity_design.md`
- Usage guide: `docs/LLM_ADAPTER_USAGE.md`

---

### Future Work (Out of Scope for Phase 1)

- **Tools parameter passthrough** in LLM adapters (e.g., Anthropic’s `tools` schema) to enable AINL graphs that call external functions directly via the LLM. This is a longer‑term alignment with AINL’s tool‑using graphs.
- **Live pricing for Anthropic/Cohere** beyond static mappings.
- **SDK‑based adapters** as an optional mode behind feature flags.
- **Automatic deprecation of `llm_query`** once the new bridge is proven stable.

This design builds on the existing merged changes and respects the repository’s boundaries. The incremental approach (bridge first, then new providers) reduces risk and delivers immediate value by enabling fallback chains for the existing OpenRouter/Ollama setup.
