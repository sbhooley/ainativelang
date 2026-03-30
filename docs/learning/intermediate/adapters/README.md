# AINL Adapters: Intermediate Guide

Adapters are how AINL talks to the outside world. This guide covers using existing adapters and building custom ones.

---

## 📦 What is an Adapter?

An **adapter** is a Python class that implements a specific interface for LLM providers or external tools.

AINL includes these built-in adapters:
- **LLM adapters**: `openrouter`, `ollama`, `mcp` (Anthropic Claude Desktop)
- **Tool adapters**: `http`, `sqlite`, `filesystem`, `cache`

You use adapters by declaring them in your graph:

```ainl
node classify: LLM("classify") {
  adapter: openrouter
  model: openai/gpt-4o-mini
  prompt: "Classify: {{input}}"
}
```

---

## 🔧 Using Built-in Adapters

### OpenRouter (Recommended for Cloud)

Multiple model access with cost tracking.

**Install**:
```bash
pip install ainl-adapter-openrouter
```

**Configure** (`~/.ainl/config.yaml`):
```yaml
adapters:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    default_model: openai/gpt-4o-mini
    base_url: https://openrouter.ai/api/v1
```

**Use in graph**:
```ainl
node chat: LLM("chat") {
  adapter: openrouter
  model: anthropic/claude-3-opus  # Any OpenRouter model
}
```

---

### Ollama (Local Models)

Run models on your own hardware.

**Install**: <https://ollama.ai> + `ollama pull llama3.3:70b`

**Configure**:
```yaml
adapters:
  ollama:
    host: http://localhost:11434
    default_model: llama3.3:70b
```

**Use**:
```ainl
node embed: LLM("embedding") {
  adapter: ollama
  model: nomic-embed-text
}
```

---

### HTTP (Universal API Client)

Call any REST API.

```ainl
node fetch: HTTP("get-weather") {
  method: GET
  url: "https://api.weather.gov/points/{{lat}},{{lon}}/forecast"
  headers: {
    "User-Agent": "AINL/1.0"
  }
}
```

Supports:
- POST, PUT, DELETE, PATCH
- JSON body templating
- OAuth2 (client credentials flow)
- Streaming responses

---

### SQLite & Filesystem

Local data access (read-only in open-core):

```ainl
node query: SQLite("query") {
  database: "./data.db"
  query: "SELECT * FROM users WHERE id = {{input.user_id}}"
  bindings: { user_id: input.user_id }
}

node write: WriteFile("log") {
  path: "./output.json"
  content: "{{node.result}}"
  mode: append
}
```

---

## 🛠️ Building a Custom Adapter

Need to connect to something not on the list? Write your own adapter in <50 lines of Python.

### Step 1: Create Python Module

```python
# my_adapter.py
from ainl.adapters import LLMAdapter, ToolAdapter
from typing import Dict, Any

class MyCustomAdapter(LLMAdapter):
    name = "mycustom"
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key")
        self.endpoint = config.get("endpoint", "https://api.example.com")
        
    def complete(self, prompt: str, model: str, **kwargs) -> str:
        """Call external LLM API and return text completion."""
        import requests
        response = requests.post(
            f"{self.endpoint}/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"prompt": prompt, "model": model, **kwargs}
        )
        response.raise_for_status()
        return response.json()["choices"][0]["text"]
    
    def validate_config(self) ->List[str]:
        errors = []
        if not self.api_key:
            errors.append("api_key required")
        return errors
```

### Step 2: Register Adapter

Create `ainl_adapters_mycustom` package:

```python
# ainl_adapters_mycustom/__init__.py
from .my_adapter import MyCustomAdapter

def register():
    return {
        "adapters": {
            "mycustom": MyCustomAdapter
        }
    }
```

### Step 3: Install & Use

```bash
pip install -e ./ainl_adapters_mycustom
```

In `ainl.yaml`:
```yaml
adapters:
  mycustom:
    api_key: ${MYCUSTOM_API_KEY}
    endpoint: https://api.example.com
```

In graph:
```ainl
node ai: LLM("process") {
  adapter: mycustom
  model: my-model-v1
  prompt: "Process: {{input}}"
}
```

---

## 🧪 Testing Adapters

Unit test your adapter:

```python
# tests/test_my_adapter.py
import pytest
from ainl_adapters_mycustom import MyCustomAdapter

def test_adapter_validate():
    adapter = MyCustomAdapter({"api_key": "test"})
    assert adapter.validate_config() == []

def test_adapter_missing_key():
    adapter = MyCustomAdapter({})
    errors = adapter.validate_config()
    assert "api_key required" in errors
```

Mock HTTP calls with `responses` library.

---

## 🔒 Adapter Best Practices

### Security

- **Never hardcode secrets** – use `${env.VAR}` or secret managers
- **Validate TLS certificates** – unless testing locally
- **Sanitize logs** – don't log API keys or PII
- **Use read-only credentials** when possible

### Reliability

- **Implement retries** – transient failures happen
- **Respect rate limits** – backoff on 429 responses
- **Timeouts** – never hang indefinitely
- **Circuit breakers** – fail fast if service is down

### Observability

- **Token counting** – track tokens used for cost attribution
- **Latency metrics** – report timings for slow adapters
- **Error classification** – distinguish client vs server errors

---

## 📊 Adapter Performance Comparison

| Adapter | Latency (p50) | Cost / 1k tokens | Max context |
|---------|---------------|------------------|-------------|
| OpenRouter (gpt-4o-mini) | 1.2s | $0.00014 | 128k |
| Ollama (llama3.3:70b) | 3.8s (CPU) | Free (local) | 8k |
| Anthropic (Claude) via MCP | 1.5s | $0.003 | 200k |
| Custom (your API) | Varies | Varies | Varies |

Measure your own with `ainl run --trace-jsonl` and parse node durations.

---

## 🐛 Debugging Adapter Issues

### "Adapter not found"

```bash
pip list | grep ainl-adapter
# Make sure package is installed
```

### "Invalid API key"

Check config: `cat ~/.ainl/config.yaml` and verify key via adapter's dashboard.

### "Connection timeout"

Increase timeout in adapter config:
```yaml
adapters:
  mycustom:
    timeout: 30  # seconds
```

### High latency

Profile nodes in trace JSONL:
```bash
grep '"node":"my_node"' run.jsonl | jq '.duration'
```

Consider:
- Local model (Ollama) for latency-critical paths
- Caching frequent responses
- Reducing prompt size

---

## 📦 Publishing Your Adapter

If you built a useful adapter, share it:

1. **Fork** <https://github.com/sbhooley/ainl-adapters>
2. **Add** your adapter under `ainl_adapters_<name>/`
3. **Test** with `pytest`
4. **Document** with README and usage example
5. **PR** against main

We'll review and publish to PyPI if it's generally useful.

---

## 🔗 Related

- [Emitter Guide](../emitters/) – Compile AINL to other targets
- [Graphs & IR](../graphs-and-ir.md) – Understand compilation
- [CLI Reference](../../reference/cli-reference.md) – Adapter-related commands

---

**Ready to build custom integrations?** Start coding your adapter →