## Runtime Compiler Contract

The canonical execution source of truth is the compiler-emitted IR consumed by `runtime/engine.py`.

- Canonical runtime: `RuntimeEngine` in `runtime/engine.py`
- Compatibility runtime: `ExecutionEngine` in `runtime/compat.py` (re-exported by `runtime.py` and `runtime/__init__.py`)
- Compiler-owned runtime helpers:
  - `compiler_v2.runtime_normalize_label_id()`
  - `compiler_v2.runtime_normalize_node_id()`
  - `compiler_v2.runtime_canonicalize_r_step()`
- Compiler-owned decoding/grammar helpers:
  - `compiler_v2.grammar_scan_lexical_prefix_state()`
  - `compiler_v2.grammar_next_slot_classes()`
  - `compiler_v2.grammar_prefix_line_ok()`
  - `compiler_v2.grammar_apply_candidate_to_prefix()`
  - `compiler_v2.grammar_active_label_scope()`
  - `compiler_v2.grammar_prefix_completable()`

### Source Of Truth

**Compile-time `include`:** Submodule sources are merged into the parent program during compilation. The runtime only sees the resulting **`labels`** map (possibly with **qualified** ids such as `retry/ENTRY`). There is no runtime `include` loader.

**Qualified vs bare label targets:** After merge, **`labels`** keys are typically **`alias/LABEL`**. Some IR edges or step fields may still name a child as a **bare** id (e.g. `_patch`). Before entering a label, **`RuntimeEngine`** resolves the target: if the bare name is not a key, it tries **`{alias}/{name}`** using the **`alias/`** prefix from the innermost stacked frame that contains a `/`. This keeps nested **If** / **Loop** / **While** / **Call** / **Jump** behavior aligned with merged includes without changing programs that already use fully qualified ids. See `runtime/engine.py` (`_resolve_label_key`).

Runtime executes compiler-emitted IR fields directly:

- Label routing and normalization via compiler-owned label helper.
- Node targeting (`Err`/`Retry` `at_node_id`) via compiler-owned node helper.
- `R` step dispatch uses compiler-canonicalized `adapter`, `target`, `args`, `out`.
- Strict graph port validation allows explicit `err`/`retry` bindings on executable
  source nodes (not just `R`) so compiler lowering and runtime retry/error handling
  remain aligned.
- Prefix-constrained decoding uses compiler-owned transition helpers so
  prefix viability/masking follows compiler law rather than duplicate heuristics.

Backward-compatible `R` fields (`src`, `req_op`, `entity`, `fields`) are folded only through `runtime_canonicalize_r_step()`.

Strict compiler dataflow policy treats bare identifier-like tokens in read positions
as variable references. String literals must be quoted in strict mode to avoid
undefined-var failures and ambiguity drift.

Covered strict migration fields include:

- `Set.ref`
- `Filt.value`
- `CacheGet.key`
- `CacheGet.fallback`
- `CacheSet.value`
- `QueuePut.value`

### Top-level `S` (service) lines and cron

Each **`S`** line is compiled to **`ir["services"][service_name] = { "mode", "path", ... }`** using **three slots** after `S`: **name**, **mode**, **path** (see `compiler_v2.py`).

For **cron-scheduled** sources the required shape is:

```text
S <adapter> cron "<cron expression>"
```

Putting extra tokens before `cron` (e.g. `S core memory cron "0 * * * *"`) mis-assigns slots so **`path` becomes the literal `cron`** and the schedule string is lost. Use **`R`** steps for `memory` / `cache` / `queue` / other adapters instead of extra `S` tokens.

Repository guardrail: `scripts/validate_s_cron_schedules.py` and `tests/test_s_cron_schedule_lines.py`. Operational context: `docs/CRON_ORCHESTRATION.md` § **`S` line shape (cron schedules)** and § **Security: queues, notifications, and secrets**.

### Legacy Compatibility Policy

- Canonical behavior is implemented only in `RuntimeEngine`.
- `ExecutionEngine` is a thin API wrapper for historical imports; it does not define independent semantics.
- Legacy adapter interfaces are bridged into canonical runtime adapters in `runtime/compat.py`.
- `_call_result` is preserved for compatibility; explicit `Call ... ->out` remains authoritative.

### Decoder Layering Contract

- `compiler_grammar.py` is formal-only orchestration (state + admissibility).
- `grammar_priors.py` is non-authoritative candidate sampling only.
- `grammar_constraint.py` composes formal state/classes + priors + pruning for compatibility APIs.
- Priors do not define formal validity.

### Graph vs Legacy Steps Execution Policy

Current policy remains graph-preferred:

- If label graph data (`nodes`, `edges`, `entry`) is present, runtime executes graph semantics.
- Step execution is retained as compatibility/fallback and for explicit `steps-only`.
- Both paths share the same op handlers where possible to reduce semantic drift.

### Graph execution pitfalls (object literals, `J`, `Set` lists)

Programs compiled to the label **graph** use the same `X`/`J`/`R` handlers as the legacy step list, but authors hit a few recurring issues:

- **`X` + `{…}` object literals:** the IR uses **`fn: "{"`**, which the runtime does not execute as “build a dict” → **`unknown X fn: {`**. Use **`core.parse`** on a JSON string, or **`X dst (obj "k" v)`** plus **`put`** chains, or other **`core.*`** / **`obj`** / **`arr`** patterns. Shared helpers live in **`modules/common/generic_memory.ainl`**.
- **`J` is not `goto`:** **`J foo`** resolves **`foo`** in the frame and **returns** that value from the current label subgraph. It does **not** transfer control to label **`foo`**. Use **`Call alias/LABEL`** or sequential nodes in one label.
- **`Set name […]`:** **`Set`** arity is **`Set <name> <single ref token>`** — a bracketed list does **not** parse as one array value. Use **`X name (arr "a" "b")`** (or similar) for lists.
- **`memory.list` optional prefix:** pass JSON **`null`** (or omit the argument in adapters that support it) for “no prefix”; a literal **`""`** is still “provided” and is **rejected** by the memory adapter. See **`docs/adapters/MEMORY_CONTRACT.md`** § 3.4.

### Trajectory logging (optional)

`RuntimeEngine` may append **one JSON line per executed step** to `<source-stem>.trajectory.jsonl` when the host enables it (CLI: `ainl run --log-trajectory`, env: `AINL_LOG_TRAJECTORY`). This is a **diagnostic artifact** only; it does not change label routing or adapter semantics. It is separate from the runner service’s HTTP audit stream (`docs/operations/AUDIT_LOGGING.md`). See `docs/trajectory.md`.

### Future Runtime Semantics Location

Any new executable semantics must be defined in compiler-owned IR shape/normalization first, then implemented in `RuntimeEngine` only.

Do not add divergent behavior to compatibility wrappers.

### Local development (Python baseline)

CI exercises **Python 3.10+**. Use a dedicated venv (e.g. `.venv-py310`) via
`scripts/bootstrap.sh` and `docs/INSTALL.md`. The pre-commit docs-contract hook
resolves `./.venv-py310/bin/python` first so local checks match that baseline
without requiring a global `python` on `PATH`.

## Verification Surface (Must Stay Green)

- Prefix alignment and transitions: `tests/test_grammar_constraint_alignment.py`
- Runtime/compiler step-schema conformance: `tests/test_runtime_compiler_conformance.py`
- Runtime behavior sanity and capability op execution: `tests/test_runtime_basic.py`
- Graph/step parity and retry/error routing: `tests/test_runtime_parity.py`, `tests/test_runtime_graph_only.py`
- Malformed `S`+`cron` schedule lines (IR `services.path` drift): `tests/test_s_cron_schedule_lines.py`

## CI gate behavior note (v1.3.3 release line)

- The `dev` extra includes runtime-service test imports (`fastapi`, `uvicorn`) so `core-pr` collection succeeds on all CI operating systems.
- Runtime benchmark JSON comparison remains part of PR visibility, but strict pass/fail enforcement is reserved for non-PR lanes where baseline hardware variance is lower.
