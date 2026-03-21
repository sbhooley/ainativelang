# What is AINL?

This page is the **docs-hub** entry for the short primer. The same narrative lives at the repository root as [`WHAT_IS_AINL.md`](../WHAT_IS_AINL.md) (some tools and agents open that path first).

**AINL** (AI Native Lang) is a **graph-canonical** programming system for deterministic AI workflows: compact source compiles to canonical **nodes/edges** IR, then the **runtime** executes with explicit adapters for I/O. It targets **AI engineers**, **agent builders**, and teams that need repeatability, validation, and auditability—not ad hoc prompt loops for every step.

For positioning, audience, and “what AINL is not,” read the root primer end-to-end. Below are **current-shipped** capabilities that matter most after **v1.2.0**.

---

## Composable workflows with includes

AINL supports **compile-time composition** via top-level **`include`**:

```ainl
include "modules/common/retry.ainl" as retry

L1: Call retry/ENTRY ->out J out
```

- The compiler **merges** the included file into the parent IR. Every label from the module is prefixed as **`alias/LABEL`** (e.g. `retry/ENTRY`, `retry/EXIT_OK`). The default alias is the included file’s stem if you omit **`as`**.
- Shared modules typically define **`LENTRY:`** (surfaced as **`alias/ENTRY`**) and one or more **`LEXIT_*:`** exits. In **strict** mode this contract is enforced so callers and agents can rely on a stable entry/exit surface.
- **Benefits for agents:** reuse **verified** subgraphs instead of regenerating long control-flow; **qualified names** in IR match the mental model (`timeout/n1`, …); fewer merge conflicts when multiple agents edit different modules.

Path resolution, cycles, and tests: `tests/test_includes.py`. Graph inspection: `docs/architecture/GRAPH_INTROSPECTION.md`.

---

## Current capabilities (v1.2 snapshot)

- **Compiler / IR:** `compiler_v2.py` → canonical **`labels`** graph (`nodes`, `edges`, `entry`, `exits`), strict-mode validation, include merge.
- **Structured diagnostics:** native **`Diagnostic`** records (lineno, spans, kinds, suggested fixes) via **`CompilerContext`**; **`ainl-validate`** and **`ainl visualize`** support **`--diagnostics-format`** (`auto` / `plain` / `rich` / `json`) and optional **rich** UI with **`pip install -e ".[dev]"`**. See `docs/INSTALL.md`, `compiler_diagnostics.py`.
- **Graph visualizer CLI:** **`ainl visualize`** / **`ainl-visualize`** / `scripts/visualize_ainl.py` emit **Mermaid** (`graph TD`, subgraph **clusters** per include alias, synthetic **`Call →` entry** edges with a `%%` comment). Paste into [mermaid.live](https://mermaid.live). Flags: `--no-clusters`, `--labels-only`, `-o -`. Details: root **`README.md`** (*Visualize your workflow*), `docs/architecture/GRAPH_INTROSPECTION.md` §7.
- **Runtime:** `ainl run`, runner service, MCP server, record/replay adapters — unchanged in role; see `docs/getting_started/README.md`. **Graph + includes:** bare child label targets in merged IR are qualified with the current **`alias/`** stack frame when needed (`runtime/engine.py`). See `docs/RUNTIME_COMPILER_CONTRACT.md`, `docs/RELEASE_NOTES.md` (v1.2.4).
- **Memory helpers (opt-in):** `modules/common/access_aware_memory.ainl` — **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, **`LACCESS_LIST_SAFE`** for optional **`last_accessed` / `access_count`** metadata on **`memory`**; use **`LACCESS_LIST_SAFE`** for graph-reliable list touches. Index: `modules/common/README.md`.

Long-form architecture: `WHITEPAPERDRAFT.md` (repository root). **Reproducible benchmarks:** [`BENCHMARK.md`](../BENCHMARK.md) (tiktoken **cl100k_base**, transparency notes) and [`docs/benchmarks.md`](benchmarks.md) (hub).

---

## Related links

| Topic | Doc |
|--------|-----|
| Install & CLI flags | `docs/INSTALL.md` |
| Graph / IR introspection | `docs/architecture/GRAPH_INTROSPECTION.md` |
| Strict / conformance | `docs/CONFORMANCE.md` |
| Integration paths | `docs/getting_started/README.md`, `docs/INTEGRATION_STORY.md` |
