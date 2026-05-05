# Architecture

Use this section to understand how AINL is structured end to end: language, compiler, canonical IR, runtime, and system boundaries.

## Key docs

- [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md) — system map
- [`GRAPH_INTROSPECTION.md`](GRAPH_INTROSPECTION.md) — graph/IR inspection, Mermaid CLI (`ainl visualize` / `ainl-visualize`), and DOT export (`render_graph.py`)
- [`COMPILE_ONCE_RUN_MANY.md`](COMPILE_ONCE_RUN_MANY.md) — compile-once/run-many proof pack
- [`../benchmarks.md`](../benchmarks.md) § *Analytical orchestration-token economics* · [`../../BENCHMARK.md`](../../BENCHMARK.md) — reproducible orchestration-token vs prompt-loop baselines
- [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md) — runtime/compiler ownership and contract

## Related sections

- Language definition: [`../language/README.md`](../language/README.md)
- Runtime behavior: [`../runtime/README.md`](../runtime/README.md)
- Schemas and contracts: [`../reference/README.md`](../reference/README.md)
