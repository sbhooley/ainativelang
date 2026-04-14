# Adapter Developer Guide

## Overview

AINL adapters allow pluggable integration with LLM providers and external tools. This guide explains how to add new adapters.

## LLM Adapters

### 1. Implement AbstractLLMAdapter

Create a file under `adapters/llm/`:

```python
from .base import AbstractLLMAdapter, LLMResponse, LLMUsage

class MyProviderAdapter(AbstractLLMAdapter):
    def __init__(self, config: dict):
        # Store config: api_key, base_url, model, max_tokens, etc.
        pass
    
    def complete(self, prompt: str, max_tokens: int = None, **kwargs) -> LLMResponse:
        # Call provider API, return LLMResponse with usage
        pass
    
    def validate(self) -> bool:
        # Quick connectivity check
        return True/False
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Return USD cost
        return 0.0
```

### 2. Register Adapter

At the bottom of your module:

```python
from ..registry import AdapterRegistry
AdapterRegistry.register_llm("myprovider", MyProviderAdapter)
```

### 3. Configuration

Users configure in `.env` or YAML:

```yaml
llm:
  provider: myprovider
  model: mymodel
  max_tokens: 800
adapters:
  myprovider:
    api_key: ${MY_API_KEY}
    base_url: https://api.myprovider.com/v1
```

### 4. Testing

Add tests in `tests/` to cover:
- Instantiation
- Validation with invalid credentials
- Cost estimation non-negative
- Mocked API success path

## Tool Adapters

### MCP Tools

1. Implement a `MCPClient` for your server type (stdio or HTTP).
2. Use `MCPRegistry.register_server(name, config)` during initialization.
3. Tools are auto‑discovered via `tools/list` and invoked via `tools/call`.

### OpenClaw Tools

1. Create functions in `adapters/tools/openclaw/tools.py` that call `OpenClawGateway.call(tool_name, args)`.
2. Register new tool names in a central mapping if needed.

## `AdapterRegistry`: `get` vs `call` (runtime embedders)

The Python runtime’s **`AdapterRegistry`** (`runtime/adapters/base.py`) holds **`RuntimeAdapter`** instances for **`ainl run`**, bridge runners, and tests.

- **`registry.get(name: str) -> RuntimeAdapter | None`** — Returns the **registered** adapter, or **`None`** if the name was never **`register`**’d. It does **not** consult the capability **allowlist** (`_allowed`). Use **`get`** for **internal wiring** that already validated grants elsewhere (for example **`RuntimeEngine`** resolving **`ainl_graph_memory`** for GraphPatch paths, or **`boot_armaraos_graph_memory`** fetching the graph-memory bridge after **`allow`/`register`**).
- **`registry.call(adapter_name, target, args, context)`** — Enforces **`adapter_name in _allowed`** before dispatch; this is the normal path for **operator-facing** adapter calls from compiled graphs.

If you add embedder code that mirrors the ArmaraOS bridge pattern, prefer **`call`** for anything that should respect host profiles; reserve **`get`** for controlled call sites that need the concrete adapter object without a second capability check. See **`docs/ARMARAOS_INTEGRATION.md`** (graph-memory / registry) and **`tests/test_armaraos_monitor_registry.py`**.

## Conformance

All adapters must pass:
- `validate()` returns `False` for unreachable or invalid credentials (without raising)
- `estimate_cost()` returns a float >= 0
- For LLM adapters, `complete()` returns an `LLMResponse` with non‑empty `content` and correct `usage` fields when successful.

## Notes

- Keep adapters stateless; store session objects if necessary within the instance.
- Use `requests.Session()` for HTTP efficiency.
- Respect timeouts; default to 60s for LLM, 30s for tools.
- Log errors with `logging` module (already configured in runtime).
