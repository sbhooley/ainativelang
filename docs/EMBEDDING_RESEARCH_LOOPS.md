# Embedding AINL in Research Loops

Use AINL as a deterministic orchestration substrate inside evolutionary or self-improving agent loops.

## In-memory Python flow

```python
from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine
from runtime.adapters.base import AdapterRegistry

ainl_source = """
S app api /api
L1: R core.ADD 2 3 ->sum J sum
"""

compiler = AICodeCompiler(strict_mode=True)
ir = compiler.compile(ainl_source, emit_graph=True)
if ir.get("errors"):
    raise RuntimeError(ir["errors"])

registry = AdapterRegistry(allowed=["core"])
engine = RuntimeEngine(ir=ir, adapters=registry, trace=True)
result = engine.run_label(engine.default_entry_label(), frame={})
trace = engine.get_trace()
```

## Loop-friendly primitives

- `ainl inspect workflow.ainl` for canonical IR snapshots.
- `ainl run workflow.ainl --trace-jsonl run.trace.jsonl` for observable execution tape.
- MCP `ainl_validate` diagnostics now include `llm_repair_hint`.
- MCP `ainl_fitness_report` and `ainl_ir_diff` provide scoring and mutation signals.

## Fitness score contract

`ainl_fitness_report` returns a bounded `metrics.fitness_score` in `[0, 1]` plus
`metrics.fitness_components` for transparency.

Current weighted formula:

- reliability: `0.6`
- latency: `0.2` (lower latency => higher component)
- steps: `0.1` (fewer runtime steps => higher component)
- adapter calls: `0.1` (fewer calls => higher component)

Use `fitness_components.weights` in tool output as the source of truth for
downstream ranking logic.

Detailed MCP payload contract: `docs/operations/MCP_RESEARCH_CONTRACT.md`.
