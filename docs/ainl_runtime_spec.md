# AI Native Lang (AINL) Runtime Spec (MVP)

Cross-reference: canonical ownership and compatibility policy are defined in
`docs/RUNTIME_COMPILER_CONTRACT.md`.

## 1) Execution Model

AINL source is parsed by the existing compiler front-end (`compile(code, emit_graph=True)`), which preserves:

- exact source text (`source.text`)
- CST line nodes with lossless tokens (`kind/raw/value/span`)
- unknown/invalid lines in `meta`

Runtime executes canonical IR directly:

- preferred: `labels[id].nodes/edges`
- fallback: `labels[id].legacy.steps`
- graph fallback to steps is allowed only when graph executed no non-meta work (e.g., Err-only path).
- graph execution is the canonical runtime path when valid graph data is present.

Execution is deterministic and side-effect constrained by capability-gated adapters.

## 2) Program Structure

- Top-level declarations configure services/types/auth/policies/capabilities.
- Label blocks (`L<n>:`) contain executable steps.
- Entry points:
  - explicit `--label <id>` from CLI, or
  - inferred endpoint label from `services.core.eps` for API use.

## 3) Values and Types

Runtime value domain:

- `null` (`None`)
- `bool`
- `int`
- `float`
- `string`
- `array` (`list`)
- `object/map` (`dict`)

All returned values are JSON-safe encoded.

## 4) Scope and Frames

- Labels execute with shared mutable frame semantics across control flow.
- `Call`, `If`, `Loop`, and `While` all execute sub-labels against the same frame (no copy-on-call).
- Return semantics:
  - callee `J var` returns a value
  - caller stores return at `_call_result` by default, or explicit `Call Lx ->out` binding when provided
- `Set` and `X` update the current frame.
- In strict mode, bare identifier-like tokens in read positions are treated as
  variable references; string literals must be quoted to avoid ambiguity.

## 5) Error Model

Typed runtime errors:

- `RuntimeError` (execution failure)
- `AdapterError` (capability/adapter refusal)
- `ValidationError` (invalid op/slots at runtime boundary)

All runtime errors include:

- label id
- step index / node id when available
- source span if present in step metadata
- call stack (`label -> label -> ...`)

Err/retry semantics:

- Runtime uses compiler-emitted node targeting (`at_node_id`) for `Err` and `Retry`.
- Explicit `@nX` bindings are authoritative; omitted `@` forms use deterministic
  previous-step attachment semantics in step-mode lowering.
- Retry replays the targeted failing step semantics (not only a hardcoded op subset).
- Error-handler recursion is rejected with explicit runtime error and failing op context.
- Graph mode follows explicit edges/ports; step mode uses explicit route maps
  derived from `Err`/`Retry` steps.

## 6) Determinism

- No implicit randomness.
- Stable sort/filter semantics for missing keys.
- Explicit time/random behavior only via capability-gated adapter ops.
- Retry behavior is explicit (`Retry count backoff_ms`).

## 7) Legacy Compatibility Mapping

Current compatibility behavior is preserved for:

- `R`, `J`, `If`, `Err`, `Retry`, `Call`, `Set`, `Filt`, `Sort`

MVP general-compute extensions:

- `X dst fn ...args` (compact compute op)
  - Supported `fn` names: `add|sub|mul|div|idiv|get|put|len|push|obj|arr|eq|ne|lt|lte|gt|gte|and|or|not|concat|join|ite|if`
  - All of the above are also accepted with a `core.` prefix (e.g. `core.add`, `core.idiv`, `core.ite`).
  - `ite`/`if`: `X dst ite cond then_val else_val` — inline conditional; returns `then_val` if `cond` is truthy, else `else_val`.
  - `idiv`: integer division (truncates toward zero).
  - S-expression paren form accepted: `X dst (fn arg…)` — the compiler strips the outer parens before emitting IR, so both forms produce identical IR.
- `Loop ref item ->Lbody ->Lafter` — alias `ForEach`
- `While cond ->Lbody ->Lafter [limit=N]`

**`J` semantics:** `J var` resolves `var` from the execution frame and returns the resolved value as the label result. If `var` is not in the frame, it is treated as a string literal. The runtime applies `_resolve(var, frame)` — do not rely on `var` being returned as a raw token string.

All ops remain space-delimited compact forms and are deterministic.

Canonical runtime implementation is `runtime/engine.py` (`RuntimeEngine`).
Compatibility API surface is `runtime/compat.py` (`ExecutionEngine`), re-exported
by `runtime.py`.

## 8) Security Model

- No Python `eval`/`exec`.
- All IO through adapter registry.
- Capability gating controls allowed adapter namespaces (`core`, `db`, `api`, etc.).
- `fs`/`http` adapters are disabled unless explicitly enabled by config.

## 9) Tracing

Optional trace mode emits per-step events:

- label, op, inputs, outputs, duration_ms
- error event with stack + span metadata

Trace emission is side-effect free and deterministic.
