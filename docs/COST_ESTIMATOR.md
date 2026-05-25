# AINL Graph Cost Estimator

Know what your graph will cost **before you run it**.

## Overview

The cost estimator performs static analysis on a compiled AINL IR graph and produces per-node, per-label, and total token/cost projections — at compile time, with zero API calls.

Implementation: `tooling/cost_estimate.py` (tiktoken when available; length/4 heuristic fallback for prompt sizing).

## CLI

```bash
# Table output (default) with gpt-4o pricing
ainl estimate my_graph.ainl

# Different model
ainl estimate my_graph.ainl --model claude-sonnet-4-6

# Summary only
ainl estimate my_graph.ainl --format summary

# Machine-readable JSON
ainl estimate my_graph.ainl --format json

# Custom run frequency for daily/monthly projections
ainl estimate my_graph.ainl --runs-per-day 24
```

Related flags on other commands (same engine):

```bash
ainl validate my_graph.ainl --estimate --json-output
ainl check my_graph.ainl --estimate
ainl inspect my_graph.ainl --estimate
```

## Supported models

Pricing is defined in `MODEL_PRICING` inside `tooling/cost_estimate.py` (USD per 1M tokens):

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| gpt-4o | 2.50 | 10.00 |
| gpt-4o-mini | 0.15 | 0.60 |
| gpt-4.1 | 5.00 | 15.00 |
| gpt-4-turbo | 10.00 | 30.00 |
| gpt-3.5-turbo | 0.50 | 1.50 |
| claude-sonnet-4-6 | 3.00 | 15.00 |
| claude-haiku-4-5 | 0.80 | 4.00 |
| claude-opus-4-6 | 15.00 | 75.00 |
| gemini-1.5-pro | 1.25 | 5.00 |
| gemini-1.5-flash | 0.075 | 0.30 |

Unknown model names fall back to `gpt-4o` pricing with a warning.

## How it works

1. **Compile** — `ainl estimate` compiles the `.ainl` source to IR (optional `--strict`).
2. **Walk IR** — Every label/node is visited; LLM adapter `R` nodes get token estimates from prompt text; other nodes show zero cost.
3. **Price** — Token counts × model rates → USD per execution.
4. **Project** — Daily/monthly totals use `--runs-per-day` (default 10).

Estimates are **static** — they do not call providers and may differ from live billing (actual prompts, caching, tool loops).

## Programmatic API

```python
from tooling.cost_estimate import estimate_ir_cost, estimate_file_cost, format_estimate_report

report = estimate_file_cost("my_graph.ainl", model="gpt-4o-mini")
print(format_estimate_report(report, style="summary"))

# From an IR dict already in memory
report = estimate_ir_cost(ir, pricing_model="claude-haiku-4-5", runs_per_day=24)
print(format_estimate_report(report, style="json"))
```

## Updating pricing

Edit `MODEL_PRICING` in `tooling/cost_estimate.py` when provider list prices change. Re-run `tests/test_cost_estimate.py` after edits.
