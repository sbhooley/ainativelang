# AI Native Lang (AINL) Runtime Semantics (Frozen MVP)

This document defines the current runtime behavior expected by tests.

## 1) Truthiness

Truthiness uses `runtime.values.truthy()` and is stable across step and graph execution.

- Used by `If`, `While`, boolean `X` ops (`and`, `or`, `not`)
- Semantics are runtime-value based (not source-token based)

Related tests:
- `tests/test_runtime_basic.py::test_runtime_if_branch`
- `tests/test_runtime_basic.py::test_runtime_x_comparisons_for_branching`

## 2) `If` Semantics

### Step mode
- Evaluates condition and calls target label (`then` or `else`)
- If branch label returns non-`None`, current label returns that value
- If branch label returns `None`, execution continues to next step

### Graph mode
- Evaluates condition and calls target label via `then`/`else` label edge
- If branch label returns non-`None`, current label returns that value
- If branch label returns `None`, graph path terminates (no implicit node fallthrough from `If`)

Related tests:
- `tests/test_runtime_graph_only.py::test_graph_if_no_value_return_does_not_fallthrough_to_linear_node`
- `tests/test_runtime_graph_only.py::test_graph_only_if_and_call_flow`

## 3) `Call` Return Routing

- `Call Lx` stores callee result in `_call_result`
- `Call Lx ->out` stores result in `out` and mirrors into `_call_result`
- Shared mutable frame semantics apply (callee mutations are visible to caller)

Related tests:
- `tests/test_runtime_basic.py::test_runtime_call_helper`
- `tests/test_runtime_basic.py::test_runtime_call_helper_with_explicit_out`
- `tests/test_runtime_basic.py::test_shared_frame_call_semantics`

## 4) `Err` Handler Rules

### Step mode
- Pre-scan seeds initial handler (supports `R ... Err ->Lx`). Canonical behavior is implemented in `runtime/engine.py` and exposed through compatibility wrappers.
- Encountered `Err` can override active handler later in the same label
- Handler is label-scoped metadata; runtime catches both `AdapterError` and other `Exception`
- **Compatibility API (`runtime.py` / `runtime.compat.ExecutionEngine`):** preserves loop-level try/except behavior so any step (not only `R`) can trigger the handler; recursion guard via call stack; handler runs with same `ctx` (including `_error`).

### Graph mode
- `err` edge handler has priority
- If no `err` edge handler, active `Err` metadata handler is used
- Same catch domain: `AdapterError` and other `Exception`

### Recursion protection
- If selected handler label is already in call stack, runtime raises:
  - `error handler recursion detected: handler=<label> failing_op=<op>`

Related tests:
- `tests/test_runtime_basic.py::test_step_mode_err_catches_when_err_after_failing_r`
- `tests/test_runtime_basic.py::test_step_mode_err_allows_later_handler_override`
- `tests/test_runtime_basic.py::test_step_mode_err_handler_recursion_is_rejected`
- `tests/test_runtime_graph_only_negative.py::test_graph_only_err_handler_recursion_is_rejected`

## 5) `Retry` Semantics

- `Retry` retries only the immediately previous `R` step/node
- Retry attempts: `max(1, count)`
- Backoff delay between failed attempts: `backoff_ms`
- Backoff strategy (optional, default `"fixed"`):
  - `"fixed"` — same delay every attempt
  - `"exponential"` — delay doubles each attempt (`backoff_ms * 2^(attempt-1)`),
    capped at `max_backoff_ms` (default 30000)
- Retries on any raised exception from the retried `R`
- In graph mode, retry path is driven by `port="retry"` edge to `Retry` node
- Syntax: `Retry [@node] count backoff_ms [strategy]`

Related tests:
- `tests/test_runtime_graph_only.py::test_graph_only_retry_port_recovers`
- `tests/test_runtime_graph_only_negative.py::test_graph_only_retry_exhaustion_raises`
- `tests/test_retry_backoff.py` — fixed/exponential backoff, cap, compiler parsing

## 6) `Loop` / `While` Return Behavior

- Loop body label return does not break the loop; non-`None` body returns are captured into `_loop_last`
- While body label return does not break loop; non-`None` body returns are captured into `_while_last`
- `While` enforces iteration limit (`limit`, default `10000`)
- Optional `after` label can return final value for the construct

Related tests:
- `tests/test_runtime_basic.py::test_runtime_loop_accumulate_updates_parent_frame`
- `tests/test_runtime_basic.py::test_runtime_while_limit_parsed_from_source`
- `tests/test_runtime_graph_only_negative.py::test_graph_only_while_limit_exceeded`

## 7) Graph/Step Mode Selection

- Runtime default is graph-preferred when a label has `nodes`, `edges`, and `entry`
- Step execution is used when graph is absent or when `force_steps=True`
- Graph-to-step fallback is allowed only when graph executed no non-meta ops (Err-only path)
- Engine-level mode policy:
  - `graph-preferred` (default)
  - `steps-only`
  - `graph-only` (requires graph data)
- Unknown-op policy:
  - `skip` (default in non graph-only modes)
  - `error` (default in graph-only mode)

Related tests:
- `tests/test_runtime_graph_only.py::test_graph_mode_is_canonical_when_graph_exists_unless_force_steps`
- `tests/test_runtime_graph_only.py::test_graph_err_only_path_can_fallback_to_steps`
- `tests/test_runtime_graph_only.py::test_graph_nonmeta_execution_does_not_step_fallback`
- `tests/test_runtime_api_compat.py::test_runtime_unknown_op_policy_error_steps_mode`

## 8) Property/Fuzz Safety Guarantees

- Step-vs-graph equivalence is property-tested on constrained op subsets
- Randomized small IRs are fuzzed for bounded, controlled runtime failures

Related tests:
- `tests/property/test_runtime_equivalence.py::test_property_steps_vs_graph_equivalence`
- `tests/property/test_runtime_equivalence.py::test_property_steps_vs_graph_side_effect_log_equivalence`
- `tests/property/test_ir_fuzz_safety.py::test_property_random_ir_runtime_safety`

## 9) Canonical Graph Node Schema (Agent-Facing)

See **docs/reference/GRAPH_SCHEMA.md** for the full Agent Graph v1 schema. Summary:

- `id`: canonical node id (`"n1"`, `"n2"`, …), contiguous per-label
- `op`: core control/effect op (`R`, `If`, `Call`, `Loop`, `While`, `J`, `Retry`, `Err`, `Set`, `X`, `Filt`, `Sort`, `CacheGet`, `CacheSet`, `QueuePut`, `Tx`, `Enf`)
- `effect`: `"io"` \| `"pure"` \| `"meta"` (e.g. `R`, `Call`, `CacheSet`, `QueuePut`, `Tx` are `io`; most others are `pure`; `Err` is `meta`)
- `reads`: list of frame keys the node reads (best-effort static analysis)
- `writes`: list of frame keys the node writes (e.g. `R` writes its `out`, `J` writes nothing)
- `lineno`: optional source line number for tooling
- `data`: the legacy step dict (lossless, including raw slots)

Edges are also canonical:

- `from`: node id
- `to`: node id or label id
- `to_kind`: `"node"` \| `"label"`
- `port`: branch kind, one of:
  - `"next"`: linear fallthrough to the next node
  - `"then"` / `"else"` for `If`
  - `"body"` / `"after"` for `Loop` / `While`
  - `"err"` for error paths
  - `"retry"` for retry paths

These fields are emitted for all compiler-built graphs and validated in strict mode so agents can query, diff, and safely rewrite graphs without re-parsing source text.

## 10) Agent-Focused Error/Trace API (Implemented)

- **Formal error schema:** `AinlRuntimeError` has `code`, `data`, and `to_dict()` returning stable fields: `code`, `message`, `label`, `step_index`, `op`, `stack`, `data`.
- **Error-code taxonomy:** `runtime.engine` defines constants (`ERROR_CODE_MAX_DEPTH`, `ERROR_CODE_ADAPTER_ERROR`, `ERROR_CODE_RUNTIME_OP_ERROR`, etc.); adapter failures use `RUNTIME_ADAPTER_ERROR`, other op/execution failures use `RUNTIME_OP_ERROR`.
- **Trace API:** `engine.get_trace()`, `engine.clear_trace()`, `engine.last_trace_event()` with a stable event shape. In **graph mode**, events also include `node_id`, `edge_taken` (port, to_kind, to), and when applicable `branch` (If: port, condition), `err_routed` (error-handler routing), `retry_attempt` (attempt, succeeded).
- **Runner contract:** `runtime.engine.run_with_debug(engine, label, frame)` returns either `{"ok": True, "result": ..., "trace": [...]}` or `{"ok": False, "error": e.to_dict(), "trace": [...]}`. Use this for autonomous repair loops; build the engine with `trace=True` to populate `trace`.
