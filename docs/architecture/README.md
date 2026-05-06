# Architecture

Use this section to understand how AINL is structured end to end: language, compiler, canonical IR, runtime, and system boundaries.

## Key docs

- [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md) — system map
- **[`TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md`](TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md)** — **platform vocabulary:** ToolRegistry, ToolPatch, PatchRegistry (host enforcement); aligns orchestration with compiled-graph grants ([`operations/CAPABILITY_GRANT_MODEL.md`](../operations/CAPABILITY_GRANT_MODEL.md)); reference wiring in sibling **ainl-inference-server**
- **[`TOOL_SURFACE_CANONICALIZATION_CHECKLIST.md`](TOOL_SURFACE_CANONICALIZATION_CHECKLIST.md)** — **implementation backlog** to canonicalize §7 (`schemas/`, compiler, runtime deny, tests)
- [`GRAPH_INTROSPECTION.md`](GRAPH_INTROSPECTION.md) — graph/IR inspection, Mermaid CLI (`ainl visualize` / `ainl-visualize`), and DOT export (`render_graph.py`)
- [`COMPILE_ONCE_RUN_MANY.md`](COMPILE_ONCE_RUN_MANY.md) — compile-once/run-many proof pack
- [`../benchmarks.md`](../benchmarks.md) § *Analytical orchestration-token economics* · [`../../BENCHMARK.md`](../../BENCHMARK.md) — reproducible orchestration-token vs prompt-loop baselines
- [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md) — runtime/compiler ownership and contract

## Related sections

- Language definition: [`../language/README.md`](../language/README.md)
- Runtime behavior: [`../runtime/README.md`](../runtime/README.md)
- Schemas and contracts: [`../reference/README.md`](../reference/README.md)
