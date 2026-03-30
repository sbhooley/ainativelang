# Graphs & Intermediate Representation (IR)

> **⚠️ DESIGN PREVIEW**: The `graph { node ... }` syntax shown in this document
> is a **design preview for AINL 2.0** and does not compile with the current
> AINL compiler (v1.3.3). The current working syntax uses single-character
> opcodes (`S`, `R`, `X`, `J`, `If`, `Set`). See `examples/hello.ainl` or
> `AGENTS.md` in the repo root for real, compilable syntax.


Deep dive into how AINL compiles graphs and how to optimize them.

---

## 🔍 What Happens When You Run `ainl`?

```
Input: mygraph.ainl
    ↓
Lexer/Parser → AST (Abstract Syntax Tree)
    ↓
Validator → Type-check, policies, cycles
    ↓
IR Generator → Canonical JSON Intermediate Representation
    ↓
Optimizer → Simplify, constant fold, eliminate dead nodes
    ↓
Emitter → Target-specific code (LangGraph, FastAPI, etc.)
    ↓
Runner → Execute on target platform
```

The **IR** is the key artifact. It's JSON, it's canonical, and it's what all emitters consume.

---

## 🧱 IR Structure

Example graph:

```ainl
graph Example {
  input: Request = { query: string }
  
  node classify: LLM("classify") {
    prompt: "Classify: {{input.query}}"
  }
  
  node route: switch(classify.result) {
    case "FOOD" -> food_handler
    case "TRAVEL" -> travel_handler
  }
  
  node food_handler: HTTP("fetch-recipe") {
    url: "https://api.example.com/recipes?q={{input.query}}"
  }
  
  node travel_handler: HTTP("fetch-flights") {
    url: "https://api.example.com/flights?from={{input.origin}}&to={{input.dest}}"
  }
  
  output: route.result
}
```

### Corresponding IR (simplified)

```json
{
  "version": "1.0",
  "name": "Example",
  "inputs": {
    "type": "object",
    "properties": {
      "query": { "type": "string" }
    },
    "required": ["query"]
  },
  "outputs": {
    "type": "object",
    "properties": {
      "result": { "type": "any" }
    }
  },
  "nodes": [
    {
      "id": "classify",
      "type": "llm",
      "config": {
        "prompt": "Classify: {{input.query}}",
        "model": "openai/gpt-4o-mini",
        "adapter": "openrouter",
        "max_tokens": 10
      }
    },
    {
      "id": "route",
      "type": "switch",
      "config": {
        "on": "classify.result",
        "cases": {
          "FOOD": "food_handler",
          "TRAVEL": "travel_handler"
        }
      }
    },
    {
      "id": "food_handler",
      "type": "http",
      "config": {
        "method": "GET",
        "url": "https://api.example.com/recipes?q={{input.query}}"
      }
    },
    {
      "id": "travel_handler",
      "type": "http",
      "config": {
        "method": "GET",
        "url": "https://api.example.com/flights?from={{input.origin}}&to={{input.dest}}"
      }
    }
  ],
  "edges": [
    { "from": "input", "to": "classify" },
    { "from": "classify", "to": "route" },
    { "from": "route", "to": "food_handler" },
    { "from": "route", "to": "travel_handler" },
    { "from": "food_handler", "to": "output" },
    { "from": "travel_handler", "to": "output" }
  ]
}
```

**View your own IR**:

```bash
ainl compile mygraph.ainl --output graph.json
cat graph.json | jq '.'
```

---

## 🎯 Why IR Matters

### 1. Debugging

If your graph behaves unexpectedly, inspect the IR to see the *actual* compiled structure (template variables resolved, default values filled).

```bash
ainl compile mygraph.ainl --output - | jq '.nodes[] | {id, type, config}'
```

### 2. Performance Optimization

The optimizer runs **before** emission. Look for:

- **Dead nodes**: Nodes with no path to output (removed automatically)
- **Constant folding**: `2+2` computed at compile time
- **Prompt token reduction**: Template variables that could be pre-computed

View optimization log:

```bash
ainl compile mygraph.ainl --optimize-level 3 --verbose
```

### 3. Static Analysis

Write tools that analyze IR for:
- Token usage estimation (sum LLM node `max_tokens`)
- Graph depth (longest path through nodes)
- Critical path (bottleneck nodes)

Example: Find expensive nodes:

```bash
cat graph.json | jq '.nodes[] | select(.type=="llm") | {id, max_tokens: .config.max_tokens}' | sort -k2 -n -r
```

---

## 🛠️ Optimization Levels

`ainl compile` supports optimization levels:

| Level | Passes Applied |
|-------|----------------|
| `-O0` | No optimization (fastest compile) |
| `-O1` | Remove dead nodes, constant folding |
| `-O2` | Merge adjacent LLM calls (if safe) |
| `-O3` | Inline small functions, aggressive inlining |
| `-Oz` | Minimize token budget (`max_tokens` reduction) |

Default: `-O2`. Use `-O0` for debugging.

Example:

```bash
ainl compile mygraph.ainl --optimize-level 3 -o optimized.json
```

---

## 📊 Token Estimation

AINL estimates **orchestration tokens** (not LLM tokens) at compile time:

```bash
ainl estimate-tokens mygraph.ainl
```

Output:
```
Graph: Example
Node estimate:
  - classify (LLM): 50 tokens (prompt) + 10 (output) = 60
  - route (switch): 5 tokens
  - food_handler (HTTP): 20 tokens
  - travel_handler (HTTP): 30 tokens
Total orchestration tokens per run: 115
```

**Orchestration tokens** areAINL's own tokens for graph execution, separate fromLLM API tokens.

---

## 🏗️ IR Schema Reference

Full schema in `docs/reference/ir-schema.json`.

Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | IR version (currently "1.0") |
| `name` | string | Graph name |
| `inputs` | JSON Schema | Input type definition |
| `outputs` | JSON Schema | Output type definition |
| `nodes` | array | Node definitions |
| `edges` | array | Connections between nodes |
| `config` | object | Global graph config (budget, timeouts) |

**Node types**:
- `llm` – Language model call
- `http` – REST API
- `sql` – SQL query (SQLite, Postgres)
- `switch` – Conditional branching
- `transform` – Data mapping (e.g., `x → x*2`)
- `file` – Read/write files
- `custom` – User-defined Python code

---

## 🧪 Graph Introspection

AINL can introspect graphs at runtime:

```bash
ainl inspect mygraph.ainl
```

Outputs:
- DAG visualization (DOT format)
- Topological sort order
- Critical path length
- Parallelism opportunities

Export to Mermaid for docs:

```bash
ainl inspect mygraph.ainl --format mermaid > graph.md
```

---

## 📈 Performance Tuning Tips

### 1. Minimize LLM Calls

Every LLM node costs tokens and latency. Strategies:

- **Caching**: Use `cache` node type for repeated queries
- **Classification first**: Use cheap model (gpt-4o-mini) to route, expensive model only on specific paths
- **Precompute**: Replace LLM nodes with deterministic logic if possible

### 2. Reduce Prompt Size

Smaller prompts = cheaper, faster.

- Use concise instructions
- Template variables only, no hardcoded examples unless essential
- Consider system vs user messages appropriately

### 3. Parallelize Independent Branches

AINL executes independent branches in parallel automatically:

```
       → A → B →
Input →         → Merge → Output
       → C → D →
```

Nodes A/B and C/D run concurrently.

Ensure branches don't share mutable state (AINL enforces DAG, so it's safe).

---

## 🐛 Common IR Issues

### "Cannot find node X"

Edge references a non-existent node. Check node IDs in IR.

### "Cycle detected"

Graph has circular dependency. AINL graphs must be DAGs.

### "Type mismatch on edge"

Output type of source node doesn't match input type of destination. Fix with `transform` node to convert.

---

## 📚 Next Steps

Now that you understand IR:

1. **Profile your graphs**: `ainl compile --verbose` to see optimization passes
2. **Reduce tokens**: `ainl optimize --aggressive mygraph.ainl`
3. **Deploy**: Choose an [emitter](emitters/) and launch your graph

---

## 🔗 Related

- [Emitter Guide](emitters/) – Compile to different platforms
- [Testing Guide](testing.md) – Test graph correctness
- [ IR Schema Reference](../../reference/ir-schema.md) – Full JSON schema

---

**Optimize your graphs and emit to production!** →