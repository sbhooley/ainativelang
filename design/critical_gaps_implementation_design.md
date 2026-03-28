# Critical Gaps Implementation Design
> **Status:** Implemented (2026-03-28)
> **Priority:** P0 (blocking production/grant demo)
> **Scope:** Wiring, cost tracking, retry, caching, tagging, deprecation

This document is the original design; behavior lives in code (`cli/main.py`, `adapters/llm_runtime.py`, `services/cost_validator.py`, etc.). The excerpts below are illustrative—see source for the canonical implementation.

## 1. LLM Adapter Registration Wiring

### Problem (historical)
`register_llm_adapters()` existed in `adapters/__init__.py` but was not wired into the CLI, so `R llm.completion ...` did not resolve without manual registration.

### Solution
Call `register_llm_adapters` during CLI startup, after config is loaded.

**Implemented in:** `cli/main.py` (adapter registry build path imports `register_llm_adapters` and passes loaded config).

**File:** `cli/main.py` (or `runtime/engine.py` if we prefer runtime-level init)

```python
# In main() after loading config YAML
from adapters import register_llm_adapters

def build_runtime(config):
    # existing registry creation
    registry = AdapterRegistry(allowed=allowed)
    # NEW: register LLM adapters from config
    register_llm_adapters(registry, config)
    # ... rest of runtime setup
    return AinlRuntime(ir, adapters=registry, ...)
```

Alternative: Add a method `AdapterRegistry.load_providers(config)` that auto-detects and calls all bootstrap funcs.

### Config Requirements
Ensure `config["llm"]` section exists with provider/model/fallback_chain (see `config.example.yaml`).

### Validation
- Boot test: `R llm.completion "test" ->x` must resolve and call underlying OpenRouter without fallback errors.
- Registry listing: `LLMAdapterRegistry.list_providers()` should return at least `openrouter` and `ollama`.

---

## 2. Automatic Cost Recording in LLMRuntimeAdapter

### Problem
LLM calls return usage but cost is not persisted automatically. Some demo `.lang` programs manually call `cost_tracker.add_cost`, but this is error-prone and inconsistent.

### Solution
Enhance `LLMRuntimeAdapter.call` to:

1. Extract `run_id` from `context` (passed by runtime during execution).
2. Call `adapter.estimate_cost(prompt_tokens, completion_tokens)` to compute cost_usd.
3. Call `CostTracker.add_cost(run_id, provider, model, prompt_tokens, completion_tokens, cost_usd)`.
4. Continue returning the standard result envelope.

**Implementation Details**

- `CostTracker` instance can be a singleton or passed via config/context. Prefer a global singleton `CostTracker()` for simplicity since it's already thread-safe.
- `RuntimeEngine` injects **`_run_id`** (UUID) on the execution frame at label entry; adapter calls receive `call_ctx = dict(frame)`, so cost recording must accept **`run_id` or `_run_id`** (tests may pass `run_id` only).
- `LLMRuntimeAdapter` must not fail if `context` is missing or no run id is present; recording is skipped (failures in `CostTracker` surface as `warnings.warn`, not hard errors).

**Modified `LLMRuntimeAdapter.call` (excerpt)**

```python
import warnings
from intelligence.monitor.cost_tracker import CostTracker

def call(self, target, args, context=None):
    ...
    resp = adapter.complete(...)
    usage = resp.usage
    provider = resp.provider
    model = resp.model

    # Automatic cost recording (run_id from context["run_id"] or context["_run_id"])
    run_id = _run_id_from_context(context)
    if run_id:
        try:
            cost = adapter.estimate_cost(usage.prompt_tokens, usage.completion_tokens)
            CostTracker().add_cost(
                run_id=run_id,
                provider=provider,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=cost
            )
        except Exception as e:
            # Log but do not fail the call (implementation uses warnings.warn)
            warnings.warn(f"Cost tracking failed: {e}")

    return {
        "content": resp.content,
        "usage": {...},
        "provider": provider,
        "model": model,
    }
```

### Testing
- Unit: Mock `CostTracker` and assert `add_cost` is called with correct args.
- Integration: Run a simple `.ainl` that calls `llm.completion`; check DB row inserted.

---

## 3. 429 Retry/Backoff for Anthropic & Cohere

### Problem
Rate limits (429) cause immediate failure. Design calls for exponential backoff with 3 attempts, 1s base.

### Solution
Implement a reusable `retry_with_backoff` decorator or utility function, then apply to `AnthropicAdapter.complete` and `CohereAdapter.complete`.

**New module:** `adapters/llm/retry.py` (or `utils/retry.py`)

```python
import time
import functools

def retry_with_backoff(max_attempts=3, base_delay=1.0, retry_statuses=(429, 500, 502, 503, 504)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except httpx.HTTPError as e:
                    status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                    if status not in retry_statuses or attempt >= max_attempts - 1:
                        raise
                    attempt += 1
                    delay = base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
        return wrapper
    return decorator
```

Apply to adapter `complete` methods:

```python
class AnthropicAdapter:
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def complete(self, prompt, max_tokens=None, **kwargs):
        ...
```

**Tests:** Extend `test_anthropic.py` and `test_cohere.py` to assert retry occurs on 429 (mock `httpx.post` to fail first call, succeed next).

---

## 4. CostValidator Caching (24h TTL)

### Problem
`services/cost_validator.py` fetches OpenRouter pricing on every invocation, potentially hitting rate limits and adding latency.

### Solution
Add an in-memory cache with 24-hour TTL. Since the validator runs periodically (via cron or scheduler), a process‑local cache is sufficient. For multi‑process setups, we can later add a file cache, but MVP uses simple dict.

**Modify `CostValidator`:**

```python
class CostValidator:
    def __init__(self):
        self._cache = {"prices": None, "fetched_at": None}
        self.cache_ttl = 24 * 3600

    def _is_cache_valid(self):
        if not self._cache["fetched_at"]:
            return False
        return (time.time() - self._cache["fetched_at"]) < self.cache_ttl

    def fetch_and_validate(self):
        if self._is_cache_valid():
            return self._cache["prices"]
        # ... existing fetch logic ...
        # Store into cache
        self._cache["prices"] = prices
        self._cache["fetched_at"] = time.time()
        return prices
```

No new dependencies; simple and safe.

### Testing
- Mock time.sleep to skip TTL; assert fetch called twice after TTL expiry.

---

## 5. Network‑Facing Tagging

### Problem
AINL security profiles may require knowing which adapters make network calls. Adapters lack consistent metadata to indicate this.

### Solution
Add a class attribute `network_facing: bool = True` to all network‑using LLM adapters (OpenRouter, Anthropic, Cohere, Ollama). Base class `AbstractLLMAdapter` can declare `network_facing = False` and subclasses override.

**In `adapters/llm/base.py`:**

```python
class AbstractLLMAdapter:
    network_facing: bool = False
    ...
```

**In each concrete adapter:**

```python
class OpenRouterAdapter(AbstractLLMAdapter):
    network_facing = True
    ...
```

Optionally: tools like `adapters/openclaw/*` also set `network_facing = True`.

**Testing:** Assertions in test files to check the attribute on each adapter class.

---

## 6. Legacy `llm_query` Deprecation Plan

### Problem
Old `llm_query` adapter remains, potentially confusing users. We need a clear migration path.

### Solution

- Add deprecation warnings when `llm_query` adapter is instantiated.
- Update documentation to point to `llm.completion` via the unified LLM adapter.
- Keep `llm_query` functional for backward compatibility for at least 2 minor releases.

**Implementation:**

```python
# adapters/llm_query.py (modified)
import warnings

class LlmQueryAdapter:
    def __init__(self, config):
        warnings.warn(
            "llm_query adapter is deprecated; use 'llm.completion' with fallback chain instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # existing init
```

**Documentation updates:**
- `docs/LLM_ADAPTER_USAGE.md` — includes **Migrating from `llm_query`** and unified `llm` registration.
- `docs/MIGRATION.md` — optional; not required for this gap list.

---

## Implementation Timeline

| Day | Tasks |
|-----|-------|
| 1 | Wire `register_llm_adapters` in CLI; add run_id to context in `RuntimeEngine`; LLMRuntimeAdapter cost recording. |
| 2 | Add `retry_with_backoff` utility; apply to Anthropic & Cohere; update tests. |
| 3 | Add `CostValidator` caching; add `network_facing` tags; deprecate `llm_query`. |
| 4 | Update docs; add integration test for full LLM call with cost recording; final pass. |

**Completed:** All rows above are implemented in-tree (see `tests/test_integration.py`, `tests/test_llm_runtime_cost_recording.py`, `tests/test_retry_backoff.py`, `tests/test_cost_validator.py`, etc.).

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| RuntimeEngine doesn't expose run id to adapters | Frame includes `_run_id` at run start; `LLMRuntimeAdapter` maps `run_id` / `_run_id` from context. |
| CostTracker not initialized in tests | Mock `CostTracker` in unit tests; SQLite store used at runtime. |
| Retry increases latency on 429 | Use jitter to avoid thundering herd; respect `Retry-After` header if present. |
| Cache poisoning on CostValidator | On fetch failure, keep old data but log error; don't overwrite cache. |

---

## Testing Checklist

- [x] `llm.completion` resolves after config-based registration (`register_llm_adapters` in `cli/main.py`; covered by `tests/test_integration.py`)
- [x] Run id available to `LLMRuntimeAdapter.call` via `context["run_id"]` or `context["_run_id"]` (`tests/test_llm_runtime_cost_recording.py`)
- [x] Cost recording path exercised in unit tests (`CostTracker.add_cost` mocked with correct args when run id present)
- [x] Retry/backoff on retryable HTTP statuses (`tests/test_retry_backoff.py`; Anthropic/Cohere adapter tests)
- [x] `network_facing` is `True` on OpenRouter/Anthropic/Cohere/Ollama; `False` on `AbstractLLMAdapter` base (`adapters/llm/*.py`)
- [x] `llm_query` emits `DeprecationWarning` on instantiation (`tests/test_llm_query_adapter.py` with `pytest.warns`)
- [x] CostValidator OpenRouter models payload cached within TTL; refetch after expiry (`tests/test_cost_validator.py`)

---

## Deliverables

- Code: as implemented in `adapters/`, `services/cost_validator.py`, `cli/main.py`, `runtime/engine.py`
- Tests: `tests/test_llm_runtime_cost_recording.py`, `tests/test_retry_backoff.py`, `tests/test_cost_validator.py` (cache + drift), `tests/test_anthropic.py`, `tests/test_cohere.py`, `tests/test_llm_query_adapter.py`, `tests/test_integration.py`
- Docs: `docs/LLM_ADAPTER_USAGE.md` (unified LLM path + **Migrating from `llm_query`** section). Optional later: `docs/MIGRATION.md` for broader deprecations
- Config: `config.example.yaml` includes an `llm:` section

---

*Original design goal: adapter maturity and a production‑ready LLM stack for demos; implementation is merged as of 2026-03-28.*
