# AINL Graph Cost Estimator

Know exactly what your graph will cost **before you run it**.

## Overview

The AINL cost estimator performs static analysis on a compiled graph IR and produces a per-node, per-label, and total token cost projection — at compile time, with zero API calls.

This is one of AINL's core economic advantages: because graphs are deterministic and compiled, their execution cost is predictable. You don't discover costs after the fact; you see them upfront.

## Usage

```bash
# Default output (table) with gpt-4o pricing
ainl estimate my_graph.ainl

# Different model
ainl estimate my_graph.ainl --model claude-sonnet-4-6

# Summary only
ainl estimate my_graph.ainl --format summary

# Machine-readable JSON
ainl estimate my_graph.ainl --format json
```

## Example Output

```
AINL Graph Cost Estimate — model: gpt-4o
────────────────────────────────────────────────────────────────────────
Label            Node                     Type                  Tokens         Cost
────────────────────────────────────────────────────────────────────────
L1               search                   x.search                   0   $0.000000
L1               classify              🤖 llm.classify              450   $0.001525
L1               gate                     gate_eval                  0   $0.000000
L1               reply                 🤖 llm.call                1100   $0.005000
L1               commit                   cursor_commit              0   $0.000000
                   LABEL TOTAL                                     1550   $0.006525
────────────────────────────────────────────────────────────────────────
GRAPH TOTAL                                              1550   $0.006525

  Daily  (10 runs/day) : $0.0653
  Monthly(10 runs/day) : $1.9575
```

## Supported Models

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4.1 | $5.00 | $15.00 |
| gpt-4-turbo | $10.00 | $30.00 |
| gpt-3.5-turbo | $0.50 | $1.50 |
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-haiku-4-5 | $0.80 | $4.00 |
| claude-opus-4-6 | $15.00 | $75.00 |
| gemini-1.5-pro | $1.25 | $5.00 |
| gemini-1.5-flash | $0.075 | $0.30 |

## How It Works

The estimator walks the compiled IR graph label by label, node by node:

1. **Node type classification** — Each node is matched against a heuristic table of typical token usage per node type. LLM nodes (e.g. `llm.call`, `llm.classify`, `rag.gen`) carry token budgets; I/O and logic nodes cost zero.

2. **Cost calculation** — Token counts × model pricing = USD cost per execution.

3. **Projections** — Daily and monthly cost projections are computed at 10 runs/day (adjustable in JSON output for custom frequencies).

## Why This Matters

A traditional agent loop has unpredictable costs because the model drives orchestration — every routing decision burns tokens. With AINL, the control flow is compiled. Only the nodes that *require* model reasoning invoke an LLM. The estimator makes this visible:

- **Zero-cost nodes**: `x.search`, `gate_eval`, `cursor_commit`, `heuristic_scores` — these run deterministically with no model invocation
- **Priced nodes**: `llm.call`, `llm.classify`, `rag.gen` — these invoke a model with known, bounded token usage

The result is full cost visibility at graph authoring time — before deployment, before execution, before any bill arrives.

## Programmatic API

```python
from tooling.cost_estimator import estimate_graph_cost, estimate_file_cost

# From a compiled IR dict
report = estimate_graph_cost(ir, model="gpt-4o-mini")
print(report.total_cost_usd)
print(report.format("json"))

# From an .ainl file path (compiles automatically)
report = estimate_file_cost("my_graph.ainl", model="claude-haiku-4-5")
print(report.format("summary"))
```

## Extending the Heuristics

Node token heuristics live in `tooling/cost_estimator.py` under `NODE_TOKEN_HEURISTICS`. Add custom node types for your adapters:

```python
NODE_TOKEN_HEURISTICS["my_adapter.call"] = {"input": 600, "output": 200}
```

Model pricing is in `MODEL_PRICING` in the same file — update as provider pricing changes.
