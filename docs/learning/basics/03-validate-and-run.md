# Validate and Run: The Strict Workflow

This guide explains AINL's **compile-time validation** system and how to debug validation failures. Understanding this is key to reliable production deployments.

## The Two-Phase Execution Model

AINL separates **validation** (compile time) from **execution** (runtime):

```bash
# Phase 1: Validation (statically check graph)
ainl validate mygraph.ainl

# Phase 2: Execution (only runs if validation passed)
ainl run mygraph.ainl --input data.json
```

**Why this matters:**
- ✅ Fail fast: Errors caught before paying for LLM calls
- ✅ Reproducibility: Same graph, same results every run
- ✅ Auditability: Validation state is part of the execution record

---

## Phase 1: Validation (`ainl validate`)

### What Gets Checked?

| Check | Description | Example Failure |
|-------|-------------|-----------------|
| **Syntax** | AINL grammar is correct | Missing `}` brace |
| **Graph structure** | All nodes reachable, no cycles | Node A → B → A (circular) |
| **Input requirements** | Input data matches schema | Input missing required field |
| **Node configuration** | Each node has needed params | LLM node missing `prompt` |
| **Type consistency** | Data types match across edges | String → expects number |
| **Policy compliance** | Meets `policy.yaml` rules | Token budget exceeded |
| **Adapter availability** | Adapters installed & configured | `adapter: foo` not installed |

### Running Validation

Basic validation:

```bash
ainl validate mygraph.ainl
```

Strict validation (recommended for CI/CD):

```bash
ainl validate --strict mygraph.ainl
```

`--strict` mode also checks:
- All LLM prompts contain template variables (no forgotten `{{var}}`)
- No unbound variables in edges
- All external resource references exist (files, env vars)

### Validation Output

**Success:**
```
✓ Graph structure valid
✓ All nodes have required inputs
✓ Type schema matches
✓ Policy constraints satisfied
```

**Failure:**
```
✗ VALIDATION FAILED
  → Line 23: Node 'classify' missing required parameter 'prompt'
  → Line 45: Undefined variable 'inputt' (did you mean 'input'?)
  → Policy violation: Token budget exceeded (estimated 12500 > max 10000)
  → Type error: output of 'parse_json' is object, but 'format_email' expects string
```

Fix errors and re-validate until all checks pass.

---

## Phase 2: Execution (`ainl run`)

Only runs if validation succeeds.

### Basic Execution

```bash
ainl run mygraph.ainl --input data.json
```

Options:

| Flag | Description |
|------|-------------|
| `--input FILE.json` | JSON input data |
| `--trace-jsonl FILE.jsonl` | Write execution trace (audit log) |
| `--budget-cost-limit USD` | Hard stop if cost exceeds |
| `--timeout DURATION` | Max execution time (e.g., `30s`, `5m`) |
| `--adapter NAME` | Override adapter from config |
| `--output FILE.json` | Save final output to file |

### Execution Trace (`--trace-jsonl`)

**Most important feature for enterprises.** Every node execution is logged as JSON lines:

```jsonl
{"node":"classify","status":"started","ts":"2025-03-30T14:22:15Z"}
{"node":"classify","status":"completed","ts":"2025-03-30T14:22:18Z","tokens_used":245,"cost":0.00061}
{"node":"alert","status":"started","ts":"2025-03-30T14:22:18Z"}
{"node":"alert","status":"completed","ts":"2025-03-30T14:22:21Z","tokens_used":187,"cost":0.00047}
{"node":"route","status":"started","ts":"2025-03-30T14:22:21Z"}
{"node":"route","status":"completed","ts":"2025-03-30T14:22:21Z","path":"send_slack"}
{"graph","status":"completed","ts":"2025-03-30T14:22:25Z","total_tokens":432,"total_cost":0.00108}
```

**Uses:**
- 🔍 Debug slow nodes (compare timestamps)
- 💰 Track token spend per execution
- 📊 Compliance audit (immutable record)
- 🚨 Alert on anomalies (node failures, cost spikes)

### Exit Codes

AINL returns appropriate exit codes for scripting:

| Code | Meaning |
|------|---------|
| `0` | Success (graph completed) |
| `1` | Validation failure |
| `2` | Execution error (node failed) |
| `3` | Timeout exceeded |
| `4` | Budget limit exceeded |
| `5` | Adapter/configuration error |

Use in CI/CD:

```bash
ainl validate mygraph.ainl || exit 1
ainl run mygraph.ainl --input test.json || exit 2
```

---

## Debugging Validation Failures

### Common Error Patterns

#### 1. "Undefined variable"

```
✗ Undefined variable: 'inputt'
```

**Cause:** Typo in variable name. AINL variables are case-sensitive.

**Fix:** Check node references and edge connections. Use the same spelling everywhere.

#### 2. "Type mismatch"

```
✗ Type error: node 'parse' returns object, but 'send' expects string
```

**Cause:** Output type of previous node doesn't match expected input.

**Fix:** Add a transform node or fix the schema:

```ainl
node format: string = "Data: {{parse.result}}"
```

#### 3. "Missing required parameter"

```
✗ Node 'llm' missing 'prompt' parameter
```

**Cause:** LLM node needs `prompt` field.

**Fix:** Add prompt with template variables:

```ainl
node classify: LLM("classify") {
  prompt: "Classify: {{input.text}}"
}
```

#### 4. "Token budget exceeded"

```
✗ Policy violation: estimated tokens 15000 > max 10000
```

**Cause:** Graph has many LLM nodes; total estimated tokens too high.

**Fix:** Lower `max_tokens` per node, simplify prompts, or increase budget in `policy.yaml`.

#### 5. "Adapter not found"

```
✗ Adapter 'mcp' not installed
```

**Cause:** Missing adapter package.

**Fix:** `pip install ainl-adapter-mcp`

---

## Using Policies to Enforce Rules

Policies are separate YAML files that define constraints. Example `policy.yaml`:

```yaml
# policy.yaml
limits:
  max_tokens_per_run: 5000
  max_cost_per_run_usd: 0.50
  max_runtime_seconds: 60

allowed_adapters:
  - openrouter
  - ollama

require_audit_trail: true  # Must use --trace-jsonl in production

deny_nodes:
  - HTTP:*.internal.*  # Block internal network access
```

Apply policy during validation:

```bash
ainl validate --policy policy.yaml mygraph.ainl
```

**Common policy rules:**
- Token budgets per environment (dev vs prod)
- Required audit logging for compliance
- Allowed tool domains (no external calls to PII APIs)
- Mandatory error handling nodes

---

## CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
name: AINL Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install AINL
        run: pip install ainl ainl-adapter-openrouter
      - name: Validate graphs
        run: |
          ainl validate --strict --policy policy.yaml graphs/*.ainl
      - name: Run unit tests
        run: |
          ainl test --suite tests/
```

Also add **execution tracing** to production runs:

```bash
ainl run production.ainl \
  --input live-data.json \
  --trace-jsonl /var/log/ainl/production-$(date +%s).jsonl \
  --budget-cost-limit 1.00
```

Upload traces to your monitoring system (Grafana Loki, Datadog, etc.).

---

## Advanced: Debug Mode

For interactive debugging, use `--debug`:

```bash
ainl run mygraph.ainl --input data.json --debug
```

This prints:
- Graph structure before execution
- Node start/completion with timing
- Intermediate values at each edge
- Full error context on failure

**Use sparingly**—debug output can log sensitive data.

---

## Schema Validation

AINL supports JSON Schema for input/output:

```ainl
graph Strict {
  input: UserRequest = {
    type: object
    properties: {
      user_id: { type: string }
      query: { type: string }
    }
    required: [user_id, query]
  }
  
  # ... nodes ...
  
  output: AgentResponse = {
    type: object
    properties: {
      answer: { type: string }
      confidence: { type: number, minimum: 0, maximum: 1 }
    }
    required: [answer]
  }
}
```

`ainl validate` checks that input JSON matches `UserRequest` schema and final output matches `AgentResponse`.

---

## Next Steps

✅ You now understand the validation and execution workflow.

Continue to **[Next Steps](../basics/04-next-steps.md)** to learn where to go from here—intermediate topics, enterprise features, and advanced patterns.

Or dive deeper:
- [Adapters](../intermediate/adapters/) – Custom LLM integrations
- [Emitters](../intermediate/emitters/) – Deploy to LangGraph/Temporal
- [Strict Mode Reference](../reference/strict-mode.md) – All validation rules
- [Execution Trace Format](../reference/trace-schema.md) – JSONL structure

---

**Stuck?** Check [Troubleshooting](#) or ask in GitHub Discussions.
