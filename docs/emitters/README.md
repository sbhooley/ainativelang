# Emitters

Use this section to understand how AINL expands into downstream artifacts such as APIs, schemas, infrastructure, and application surfaces.

## Current anchors

- [`TARGETS_ROADMAP.md`](../runtime/TARGETS_ROADMAP.md) — target/runtime support map
- [`../reference/TOOL_API.md`](../reference/TOOL_API.md) — compile/validate/emit loop contract

## Hyperspace agent emitter

Emit a **single-file Python agent** that embeds the compiled IR and runs it with `RuntimeEngine`, registering local **`vector_memory`** and **`tool_registry`** adapters and an optional `hyperspace_sdk` import stub.

**Command** (from repo root, typical):

```bash
python3 scripts/validate_ainl.py path/to/workflow.ainl --strict --emit hyperspace -o hyperspace_agent.py
```

`ainl-validate` exposes the same `--emit hyperspace` when invoked as the validate entrypoint (see root `README.md`).

**Run the emitted file** from a working tree that contains `runtime/engine.py` and `adapters/` (usually **repo root**), e.g. `python3 hyperspace_agent.py`, so imports resolve.

**Trajectory:** emitted agents honor `AINL_LOG_TRAJECTORY` / runtime trajectory hooks; JSONL is written relative to the process cwd (see [`../trajectory.md`](../trajectory.md)).

**Happy-path demo:** `examples/hyperspace_demo.ainl` — compare with `ainl run … --enable-adapter vector_memory --enable-adapter tool_registry --log-trajectory` as in root `README.md`.

**Optional (not registered by this emitter):** tiered repo context via **`code_context`** — see [`../adapters/CODE_CONTEXT.md`](../adapters/CODE_CONTEXT.md) and `examples/code_context_demo.ainl`; enable with `--enable-adapter code_context` when running graphs that call it.

## Where to see emitters in action

- Snapshot tests for emitted artifacts: `tests/test_snapshot_emitters.py`
- End-to-end API example using emitters: `examples/web/basic_web_api.ainl`

## Related sections

- Language definition: [`../language/README.md`](../language/README.md)
- Architecture and IR: [`../architecture/README.md`](../architecture/README.md)
- Example support framing: [`../examples/README.md`](../examples/README.md)
- Adapters (memory, vector_memory, tool_registry, code_context): [`../adapters/README.md`](../adapters/README.md)
