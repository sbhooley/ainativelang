## Compile Once, Run Many (Proof Pack)

This document is a **small, reproducible proof pack** that shows how AINL already supports:

- compile-once / run-many operation
- zero runtime LLM dependency
- deterministic graph-based execution
- replayable adapter-driven runs
- auditable graph/IR artifacts

It does **not** introduce new semantics; it only packages existing tools and tests.

---

### 1. Ingredients (what already exists)

- **Compiler / IR emission**
  - `compiler_v2.AICodeCompiler` — graph-first compiler.
  - `scripts/validate_ainl.py` / `ainl-validate` — CLI validator/IR emitter.
  - `docs/reference/IR_SCHEMA.md`, `docs/reference/GRAPH_SCHEMA.md` — IR + graph schema.
  - `graph_semantic_checksum` — canonical semantic checksum (see `tooling/ir_canonical.py` and `tests/test_snapshot_compile_outputs.py`).

- **Runtime / deterministic graph execution**
  - `runtime/engine.py` (`RuntimeEngine`) — executes label graphs (`execution_mode="graph-preferred"`).
  - `tests/test_snapshot_runtime_paths.py` — runtime path snapshots (fixed input → expected result + trace ops).

- **Emitters / snapshot parity**
  - `tests/test_snapshot_compile_outputs.py` — compile snapshots (graph checksum, labels, services, emit_capabilities).
  - `tests/test_snapshot_emitters.py` — emitter snapshots (server, OpenAPI, Prisma, SQL).

- **Record / replay (no live side effects)**
  - `ainl run ... --record-adapters calls.json`
  - `ainl run ... --replay-adapters calls.json`
  - Documented in `docs/INSTALL.md` and `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md`.

- **Size benchmark (optional)**
  - `BENCHMARK.md`, `scripts/benchmark_size.py`, `tooling/benchmark_size.json`.
  - Shows reproducible size ratios; **not** required for the minimal proof recipe.

---

### 2. Minimal reproducible proof recipe

This section shows a concrete, end-to-end sequence you can run locally to prove:

1. compile once to graph IR (with checksum),
2. run with live adapters,
3. replay deterministically from recorded adapter calls,
4. inspect runtime traces and graph paths,
5. do all of this without any runtime LLM involvement.

You can use any small example; here we’ll assume `examples/hello.ainl` or a simple HTTP/DB example such as `examples/web/basic_web_api.ainl`.

#### 2.1 Compile once and inspect IR (with semantic checksum)

```bash
ainl-validate examples/hello.ainl --strict --emit ir > ir.json
```

Check in `ir.json`:

- `"errors": []` (or omitted),
- `labels` and `services` are populated,
- `graph_semantic_checksum` is present and stable for this program.

This proves that:

- the program compiles to a **graph IR**,
- the graph has a deterministic semantic checksum.

If you prefer the repository script directly:

```bash
python scripts/validate_ainl.py examples/hello.ainl --strict --emit ir
```

#### 2.2 Run once with live adapters and record calls

Pick an example that uses an adapter (e.g. HTTP). For illustration:

```bash
ainl run examples/web/basic_web_api.ainl --json \
  --enable-adapter http \
  --http-allow-host api.example.com \
  --http-timeout-s 5 \
  --record-adapters calls.json
```

This:

- executes the compiled graph via `RuntimeEngine`,
- performs real adapter calls (here, HTTP),
- writes the adapter interactions to `calls.json`.

No LLM is involved at runtime; execution is graph + adapters only.

#### 2.3 Replay deterministically from recorded adapter calls

Now replay the same program, but with **no live HTTP**:

```bash
ainl run examples/web/basic_web_api.ainl --json \
  --replay-adapters calls.json
```

This run:

- uses the same compiled graph,
- replays adapter responses from `calls.json`,
- produces the same logical result for that recorded trace,
- still does not call any LLM at runtime.

Together, 2.2 + 2.3 demonstrate:

- **compile-once / run-many** for a fixed adapter trace,
- **zero runtime LLM dependency**,
- **deterministic replays** for recorded adapter interactions.

#### 2.4 Inspect runtime behavior via snapshot tests (optional)

To see how this is tested in CI, inspect:

- `tests/fixtures/snapshots/runtime_paths.json`
- `tests/test_snapshot_runtime_paths.py`

Those fixtures and tests show:

- code + input_frame → expected `result`,
- expected `trace_ops` sequence (ops executed under `trace=True`),
- `RuntimeEngine.run(..., execution_mode="graph-preferred")` is used.

Running just that test (when `pytest` is available) verifies that:

- for a catalog of programs and inputs,
- runtime results and traces remain stable over time.

#### 2.5 Summarize multiple runs (optional)

If you save one or more `RuntimeEngine.run(..., trace=True)` JSON payloads to disk,
you can compute a small health summary across them with:

```bash
python scripts/summarize_runs.py run1.json run2.json ...
```

This prints a JSON object with:

- `run_count` / `ok_count` / `error_count`
- `runtime_versions`
- `result_kinds` (Python type names of the `result` field)
- `trace_op_counts` (how many times each `op` appeared in traces)
- `label_counts` (how many trace events per label)
- `timestamps_present` (currently `false`, since run payloads do not include timestamps)

This script is tooling-only and does **not** change any language, compiler, or
runtime semantics; it simply aggregates information already present in the
saved run payloads.

---

### 3. How this relates to other evidence

- **Graph/IR introspection**  
  - `docs/architecture/GRAPH_INTROSPECTION.md` shows how to:
    - emit IR/graph with `ainl-validate` / `scripts/validate_ainl.py`,
    - query graphs with `tooling/graph_api.py`,
    - normalize and diff graphs.

- **Autonomous ops playbook**  
  - `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md` documents:
    - compile-once / run-many patterns,
    - deterministic replay (`--record-adapters`, `--replay-adapters`),
    - cooldown and remediation patterns using existing adapters.

- **Snapshot tests**  
  - `tests/test_snapshot_compile_outputs.py` guards semantic checksums, labels, services, and emit capabilities.
  - `tests/test_snapshot_emitters.py` guards emitted artifacts for server / OpenAPI / Prisma / SQL.
  - `tests/test_snapshot_runtime_paths.py` guards runtime results and trace ops.

Taken together, the reproducible recipe above plus these existing tests form an **evidence pack** that AINL already functions as a:

- compile-once / run-many substrate,
- graph-first deterministic execution engine,
- adapter-driven system with record/replay,
- auditable IR/graph + runtime behavior environment.

