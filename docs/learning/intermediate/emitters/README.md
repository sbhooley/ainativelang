# AINL Emitters: Compile to Any Target

Emitters transform your AINL graph into executable code for other platforms.

---

## 🎯 Why Use Emitters?

**Write once, deploy anywhere**

AINL graphs are portable. Write your workflow logic in AINL, then emit to:

| Target | Use Case |
|--------|----------|
| `langgraph` | Use LangGraph's state persistence and streaming |
| `temporal` | Durable workflows with Docker containers |
| `fastapi` | REST API with OpenAPI docs |
| `react` | Interactive UI from graph state |
| `openclaw` | Run as Hermes skill (existing OpenClaw users) |

**Example**: Same monitoring graph deployed both as Temporal workflow (for durable execution) and as FastAPI endpoint (for ad-hoc queries).

---

## 📦 Built-in Emitters

### LangGraph Emitter

```bash
ainl emit monitor.ainl --target langgraph -o graph.py
```

Outputs a LangGraph `StateGraph` that you can run with `graph.invoke()`.

**Features preserved**:
- Conditional branching (`switch`)
- LLM node calls (reuse your existing adapters)
- State schema

**Limitations**:
- AINL's strict validation not enforced in LangGraph runtime
- Some edge features (e.g., graph introspection) limited

---

### Temporal Emitter

```bash
ainl emit workflow.ainl --target temporal -o workflow/
```

Generates a Temporal `Workflow` and `Activity` definitions.

**Deploy**:
1. Package generated code with Temporal client
2. Register workflow and activities
3. Start Temporal worker

**Best for**: Long-running workflows (> minutes), durable state, retries with backoff.

---

### FastAPI Emitter

```bash
ainl emit api.ainl --target server -o server.py
```

Creates a FastAPI app:
- POST `/execute` – run graph with JSON input
- GET `/schema` – OpenAPI/Swagger docs
- GET `/health` – liveness probe

**Run**:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Features**: Auto-generated docs, CORS configurable, middleware support.

---

### React Emitter (Experimental)

```bash
ainl emit ui.ainl --target react -o ui/
```

Generates React components that mirror your graph structure.

Node states become component states; edges trigger re-renders.

**Early preview** – expect breaking changes.

---

## 🔧 How Emitters Work

### Compilation Pipeline

```
AINL Source
    ↓
    Parse → IR (Intermediate Representation)
    ↓
    Validate (type check, policies)
    ↓
    Emit → Target-specific code
    ↓
    Deploy → Run on target platform
```

The **IR** is the canonical representation. All emitters share the same validated IR, ensuring correctness across targets.

---

## 📊 Emitter Comparison

| Feature | Native AINL | LangGraph | Temporal | FastAPI |
|---------|-------------|-----------|----------|---------|
| Deterministic execution | ✅ | ❌ (prompt-based) | ⚠️ (depends) | ❌ |
| Compile-time validation | ✅ | ❌ | ✅ | ✅ |
| Durable state | ❌ (ephemeral) | ✅ | ✅ | ❌ |
| HTTP API | ❌ (use FastAPI) | ❌ | ❌ | ✅ |
| Long-running workflows | ❌ | ⚠️ (streaming) | ✅ | ❌ |
| Ecosystem integration | Native | Extensive | Enterprise | REST clients |

Choose emitter based on deployment target and required features.

---

## 🎨 Emitter Configuration

Most emitters accept configuration:

```bash
ainl emit graph.ainl \
  --target fastapi \
  --output server.py \
  --config fastapi.yaml
```

Example `fastapi.yaml`:
```yaml
title: "My AINL API"
version: "1.0.0"
cors:
  origins: ["https://myapp.com"]
  methods: ["POST"]
middleware:
  - auth: true  # Add JWT validation
  - rate_limit: 100/minute
```

---

## 🧪 Testing Emitted Code

AINL validates `hello.ainl` before emitting, but also test emitted artifact:

```bash
# Validate graph first
ainl validate hello.ainl

# Emit
ainl emit hello.ainl --target fastapi --output server.py

# Start server (for FastAPI)
uvicorn server:app --port 8001 &

# Test
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{"input":"test"}'

# Stop server
pkill -f uvicorn
```

Automate in CI/CD:

```yaml
- name: Validate
  run: ainl validate graphs/*.ainl
- name: Emit to FastAPI
  run: ainl emit graphs/api.ainl --target fastapi --output api_server.py
- name: Integration test
  run: |
    uvicorn api_server:app --port 8001 &
    sleep 2
    curl -f http://localhost:8001/health
    pkill -f uvicorn
```

---

## 🐛 Debugging Emitted Code

### Graph validates but emitted code fails

AINL validation checks only the graph structure, not emitter-specific issues (e.g., port in use, missing dependencies).

**Fix**: Test emitted artifact in isolation.

### Runtime error in emitted LangGraph

LangGraph adds its own state management. Ensure your graph doesn't have side effects in node bodies that assume single execution.

**Fix**: Keep nodes pure (output depends only on inputs).

### FastAPI returns 422 (validation error)

Input JSON doesn't match graph's input schema.

**Fix**: Check generated OpenAPI spec at `/docs` for expected format.

---

## 🏗️ Advanced: Custom Emitter

Need a new target? Build your own emitter.

### Skeleton

```python
# my_emitter.py
from ainl.ir import GraphIR
from ainl.emitters import Emitter

class MyEmitter(Emitter):
    name = "myemitter"
    
    def emit(self, ir: GraphIR, config: dict) -> str:
        """Generate code for target platform."""
        code = []
        code.append("# Generated by AINL MyEmitter")
        code.append(f"# Graph: {ir.name}")
        
        # Iterate nodes
        for node in ir.nodes:
            code.append(self._emit_node(node))
        
        return "\n".join(code)
    
    def _emit_node(self, node) -> str:
        if node.type == "llm":
            return f'def {node.id}():\n    return llm_call("{node.config.prompt}")'
        # ... other node types
```

Register in package `ainl_emitters_myemitter` → `ainl emit --target myemitter`.

---

## 📈 When to Use Which Emitter

| Scenario | Recommended Emitter |
|----------|---------------------|
| API endpoint | FastAPI |
| Durable workflow (hours/days) | Temporal |
| Existing LangGraph app | LangGraph (gradual migration) |
| Interactive dashboard UI | React (experimental) |
| Running on Hermes/OpenClaw | openclaw |
| Need maximum portability | Native `ainl run` (no emitter) |

**Default**: Use native `ainl run` unless you need specific target features.

---

## 📂 Example Workflow

1. **Develop**: Write `monitor.ainl` locally
2. **Validate**: `ainl validate monitor.ainl`
3. **Emit**: `ainl emit monitor.ainl --target fastapi --output api.py`
4. **Deploy**: Deploy `api.py` to your cloud (AWS ECS, GCP Cloud Run)
5. **Monitor**: Execution traces automatically sent to your logging system

Change target? Re-emit and redeploy. Same graph, different platform.

---

## 🔗 Related

- [Graphs & IR](../graphs-and-ir.md) – Understand the intermediate representation
- [ CLI Reference](../../reference/cli-reference.md) – `ainl emit` options
- [ Testing](../../learning/intermediate/testing.md) – Test emitted code

---

**Choose your target and emit your graph today!** →