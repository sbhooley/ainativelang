# Hybrid deployments: decision guide

One-page reference for choosing **pure AINL** vs **LangGraph** vs **Temporal** when integrating external orchestration.

## Quick comparison

| | **Pure AINL** | **LangGraph hybrid** | **Temporal hybrid** |
|---|---------------|----------------------|---------------------|
| **You keep** | Full stack in AINL + CLI/runner/MCP | LLM nodes, checkpoints, cyclic graphs in LangGraph | Retries, timeouts, long-running workflows in Temporal |
| **AINL holds** | Entire program | Deterministic policy graph (one or more embedded runs) | Same (typically one activity = full IR run) |
| **Durability** | Process / your infra | LangGraph checkpointer | Temporal server history |
| **Typical deps** | None extra | `langgraph` (generated wrapper) | `temporalio` (worker + workflow import) |
| **Emit / entry** | `ainl run`, MCP, emitted server | `validate_ainl.py --emit langgraph` | `validate_ainl.py --emit temporal` |

## Decision tree (markdown)

```text
Need multi-day workflows, cross-restart guarantees, or enterprise workflow UI?
├─ YES → Prefer Temporal hybrid (activity wraps AINL IR)
│         See docs/hybrid_temporal.md + examples/hybrid/temporal_durable_ainl/
└─ NO
   └─ Need cyclic LLM+tool graphs, LangGraph checkpoints, or LangChain ecosystem?
      ├─ YES → Prefer LangGraph hybrid (single ainl_core node to start)
      │         See docs/hybrid_langgraph.md + examples/hybrid/langgraph_outer_ainl_core/
      └─ NO → Prefer pure AINL (CLI, runner, hyperspace emit, MCP)
                See README.md + docs/getting_started/
```

**LangChain / CrewAI tools only:** use the **`langchain_tool`** adapter (`--enable-adapter langchain_tool`) with `R langchain_tool...` — no graph emitter required. See `examples/hybrid/langchain_tool_demo.ainl` and `docs/reference/ADAPTER_REGISTRY.md`.

## Examples (repo)

| Goal | Folder |
|------|--------|
| LangGraph wrapper + regen | [`examples/hybrid/langgraph_outer_ainl_core/`](../examples/hybrid/langgraph_outer_ainl_core/) |
| Temporal activity + workflow + regen | [`examples/hybrid/temporal_durable_ainl/`](../examples/hybrid/temporal_durable_ainl/) |
| LangChain tool bridge | [`examples/hybrid/langchain_tool_demo.ainl`](../examples/hybrid/langchain_tool_demo.ainl) |

## Deep links

- LangGraph: [`docs/hybrid_langgraph.md`](hybrid_langgraph.md)
- Temporal: [`docs/hybrid_temporal.md`](hybrid_temporal.md)
- Runtime contract: [`docs/RUNTIME_COMPILER_CONTRACT.md`](RUNTIME_COMPILER_CONTRACT.md)
- Hybrid folder overview: [`examples/hybrid/README.md`](../examples/hybrid/README.md)
- PyPI extras, pins, import paths, and stable surface: [`docs/PACKAGING_AND_INTEROP.md`](PACKAGING_AND_INTEROP.md)
- Shipping and version bumps: [`docs/RELEASING.md`](RELEASING.md)
- Production checklists (pins, PYTHONPATH, triage): [`docs/hybrid/OPERATOR_RUNBOOK.md`](hybrid/OPERATOR_RUNBOOK.md)

## DSL: opt hybrid into `minimal_emit`

Benchmarks and planners use **`minimal_emit`** when you want the smallest relevant emitter set. By default the compiler does **not** set **`needs_langgraph`** / **`needs_temporal`** unless you declare it:

```text
S hybrid langgraph
S hybrid temporal
S hybrid langgraph temporal
```

Targets are de-duped; order on the line does not matter. Unknown tokens are errors in **strict** mode. **`full_multitarget`** still includes hybrid wrappers regardless.

## Validator flags (reminder)

```bash
python3 scripts/validate_ainl.py workflow.ainl --emit langgraph -o my_langgraph.py
python3 scripts/validate_ainl.py workflow.ainl --emit temporal -o ./out/
```

`langgraph` and `temporal` are included in benchmark **`full_multitarget`** (see `tooling/emit_targets.py`). For **`minimal_emit`**, they are included only when the IR requests them—via **`emit_capabilities`** from a normal compile, or legacy IRs with **`services.hybrid.emit`**, or by authoring **`S hybrid …`** as above. CLI **`--emit langgraph` / `--emit temporal`** always works from `validate_ainl.py` regardless.
