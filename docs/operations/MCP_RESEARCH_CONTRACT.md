# MCP Research Contract (Hyperagent Pack)

This document defines additive MCP tool contracts intended for self-improving research loops.

## Stability note (v1.2.8)

The following fields are considered stable in the v1.2.7+ research pack surface (current **`RUNTIME_VERSION`** **1.2.8**):

- `ainl_validate(...).diagnostics[].llm_repair_hint`
- `ainl_ir_diff(...).diff.changed_nodes[]` as a list of `{label_id, node_id, changes}`
- `ainl_fitness_report(...).metrics.fitness_score`
- `ainl_fitness_report(...).metrics.fitness_components.weights`

Future versions may add fields but should not remove or rename these without a versioned migration note.

## Tools

- `ainl_validate(code, strict=True)`
  - Returns: `ok`, `errors`, `warnings`, `diagnostics[]`
  - Contract: each diagnostic includes `llm_repair_hint`.

- `ainl_ir_diff(file1, file2, strict=True)`
  - Returns: `ok`, `diff`
  - `diff` keys: `added_nodes`, `removed_nodes`, `changed_nodes`, `added_edges`, `removed_edges`, `rewired_edges`, `human_summary`.
  - Contract: `changed_nodes` includes payload-level `data` deltas when node op shape is unchanged but node data changed.

- `ainl_fitness_report(file, runs=5, strict=True)`
  - Returns: `ok`, `metrics`, `sample_runs`, `last_error`
  - `metrics` keys:
    - `latency_ms`, `step_count`, `adapter_calls`
    - `memory_deltas` (trace-derived frame-key proxy)
    - `operation_histogram`
    - `token_use_estimate`
    - `reliability_score`
    - `fitness_score` in `[0,1]`
    - `fitness_components` with explicit component values and `weights`

## Scoring stability guidance

- Treat `fitness_components.weights` as the live source of truth.
- Consumers should not hard-code weight constants without checking the payload.
- Rank by `fitness_score`; use component breakdown for tie-breaks and debugging.
