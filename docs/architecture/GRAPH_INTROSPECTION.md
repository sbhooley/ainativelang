## Graph and IR introspection (for agents and humans)

**Goal:** show how to inspect AINL's compiled IR/graph **today** using existing tools, without adding new semantics.

This is the recommended entry point for agents and humans who want to:

- understand **what will execute**
- see **which effects** (io vs pure vs meta) are involved
- inspect **branching and exits**
- diff and rewrite graphs safely

Programs that use **`include … as alias`** produce **qualified** label ids (`retry/ENTRY`, …) in **`ir["labels"]`**; the same graph is what **`ainl visualize`** renders as Mermaid clusters (see §7).

### 1. Get IR/graph from the CLI

The primary CLI is `ainl-validate` (installed by `scripts/bootstrap.sh` or `pip install -e .[dev,web]`).

- **Emit IR JSON (default):**

```bash
ainl-validate examples/status_branching.ainl
```

This prints the full IR object, including:

- `labels` (nodes, edges, optional `emit_edges`, entry, exits, legacy.steps)
- `services` (endpoints -> labels)
- `errors` / `warnings` / `diagnostics`
- `graph_semantic_checksum`

Equivalent using the repository script:

```bash
python scripts/validate_ainl.py examples/status_branching.ainl --emit ir
```

- **Strict validation (graph semantics checks):**

```bash
ainl-validate --strict examples/status_branching.ainl
```

This runs strict graph validation (unique entry, exits, reachability, effect typing, etc.) and still emits the same IR shape on success.

On **strict failure**, the validator prints **structured diagnostics** to **stderr** (numbered list, source context, span underlines, suggestions). Use **`--json-diagnostics`** for JSON-only stdout for automation. Optional **rich** output requires `pip install -e ".[dev]"` (see `docs/INSTALL.md`).

- **Non-JSON debug view (for quick eyeballing):**

```bash
python scripts/validate_ainl.py examples/status_branching.ainl --emit ir --no-json
```

### 2. How to read the IR for control flow

Cross-reference:

- `../reference/IR_SCHEMA.md` - top-level IR overview
- `../reference/GRAPH_SCHEMA.md` - canonical graph/label/edge schema

Key fields for control-flow and effects:

- `ir.labels[label_id].entry` - starting node id for the label.
- `ir.labels[label_id].nodes[*]` - each node has:
  - `id` - canonical `n1`, `n2`, ...
  - `op` - `R`, `If`, `J`, `Set`, `Err`, `Retry`, `Call`, ...
  - `effect` / `effect_tier` - `"pure"` vs `"io"` vs `"meta"`.
  - `reads` / `writes` - frame keys used/defined.
  - `lineno` - link back to source for audits.
  - optional `memory_type` - on **`R`** nodes for dotted graph-memory / persona verbs (`episode`, `semantic`, `procedural`, `persona`); see **`../reference/GRAPH_SCHEMA.md`**.
- `ir.labels[label_id].edges[*]` - control-flow edges:
  - `from`, `to`, `to_kind`
  - `port` - `"next"`, `"then"`, `"else"`, `"err"`, `"retry"`, `"body"`, `"after"`, `"handler"`.
- `ir.labels[label_id].emit_edges[*]` (when present) - data-flow + emit routing, separate from control-flow:
  - `port` **`"data"`** - producer **`R` / `Set`** → linear **`next`** successor; includes `var`.
  - `port` **`"emit"`** - exit **`J`** → literal **`emit_target`**; includes `var` and `target` (emit platform).
- `ir.labels[label_id].exits[*]` - `J` nodes and their return vars.

For autonomous agents, the recommended pattern is:

1. Use `nodes[*].op`, `effect`, `reads`, `writes`, and `edges[*].port` to understand control-flow and side-effects.
2. Treat `legacy.steps` as **compatibility serialization only**; the graph (`nodes`/`edges`) is canonical.

### 3. Programmatic graph API

For more structured queries, use the graph helpers described in `../reference/GRAPH_SCHEMA.md`:

- `tooling/graph_api.py` (implementation)
  - `label_nodes(ir, label_id | sequence)` / `label_edges(ir, label_id | sequence)` — merged when a **sequence** of label ids is passed
  - `emit_edges`, `data_flow_edges`, `memory_nodes` — emit topology and typed memory nodes (optional `memory_type` filter)
  - `successors(ir, label_id, node_id)`
  - `predecessors(ir, label_id, node_id)`
  - `io_nodes(ir, label_id)`
  - `nodes_using_adapter(ir, label_id, adapter_prefix)`
  - `error_paths(ir, label_id, from_node=None)`
  - `exit_nodes(ir, label_id)`

Usage sketch (Python):

```python
from compiler_v2 import AICodeCompiler
from tooling import graph_api

c = AICodeCompiler(strict_mode=True)
ir = c.compile(open("examples/status_branching.ainl").read(), emit_graph=True)

nodes = graph_api.label_nodes(ir, "1")
edges = graph_api.label_edges(ir, "1")
io_nodes = graph_api.io_nodes(ir, "1")
```

This is enough for an autonomous agent to:

- list all **io nodes** in a label
- compute **possible paths** (via `successors` / `error_paths`)
- locate all uses of a given **adapter** (`nodes_using_adapter`)
- identify **exits** and their return vars (`exit_nodes`)

### 4. Quick human summary helper

If you want a **one-line human-oriented summary** of a program without reading full IR JSON, use:

```bash
python scripts/inspect_ainl.py examples/hello.ainl
python scripts/inspect_ainl.py --strict examples/web/basic_web_api.ainl
```

This script:

- compiles to graph IR (optionally strict),
- prints `graph_semantic_checksum`,
- counts labels and nodes (by `effect`),
- lists adapters used (by adapter prefix),
- lists HTTP/DB endpoints (from `services.core.eps`),
- reports diagnostics and warnings.

It is a thin wrapper around `AICodeCompiler` and `graph_semantic_checksum` and does **not** change any semantics.

### 5. Diff, normalization, and safe rewrites

The following helpers are available for more advanced workflows (all already exist today; this section only documents them):

- **Normalization:** `tooling/graph_normalize.normalize_graph(ir)`
  - fills in missing `effect` / `reads` / `writes` / edge `port`s for legacy IR
  - produces a copy that is safer for analysis without changing semantics.

- **Diff:** `tooling/graph_diff.graph_diff(old_ir, new_ir)`
  - machine-readable summary of added/removed/changed nodes and edges.

- **Safe edits:** helpers mentioned in `../reference/GRAPH_SCHEMA.md`:
  - `insert_node_after`, `rewire_edge`, `wrap_r_with_retry`, `attach_err_handler`
  - pattern: clone IR -> edit clone -> validate -> inspect diff -> accept or discard.

These are intended for **tooling/agent use**, not for changing runtime semantics.

### 6. Record/replay and deterministic runs

For runtime-level introspection without live side-effects, use the **record/replay** flags described in `../INSTALL.md`:

- Record adapter calls:

```bash
ainl run app.ainl --json \
  --enable-adapter http \
  --record-adapters calls.json
```

- Replay deterministically (no live io):

```bash
ainl run app.ainl --json \
  --replay-adapters calls.json
```

This, combined with graph inspection, lets agents:

- reason about **possible** execution paths from IR
- observe **actual** executed paths via record/replay and logs
- compare the two to detect unexpected behavior.

### 7. Mermaid diagram (CLI visualizer)

For a **flowchart** you can paste into [mermaid.live](https://mermaid.live), GitHub, or Obsidian, use the graph visualizer (strict compile, read-only):

```bash
ainl visualize examples/hello.ainl --output - > hello.mmd
# or
ainl-visualize examples/status_branching.ainl -o diagram.md
# or from repo root without install:
python3 -m cli.main visualize examples/hello.ainl --output - > hello.mmd
python3 scripts/visualize_ainl.py examples/hello.ainl -o -
```

Behavior (see root `README.md` → **Visualize your workflow** for the full walkthrough):

- Reads `.ainl` / `.lang`, compiles with `emit_graph=True` and **strict** diagnostics on failure (same structured stderr path as `ainl-validate` when **rich** is installed).
- Emits **Mermaid** `graph TD` from canonical **`ir["labels"]`** (nodes, edges, entry); `include … as alias` labels are grouped into **subgraph** clusters by alias prefix.
- Draws **synthetic** `Call → callee entry` edges (with a `%%` comment in the output) when the IR does not list them explicitly, so included modules stay visible.
- Flags: `--no-clusters`, `--labels-only`, `--format dot` (DOT not implemented yet; use `render_graph.py` below for Graphviz DOT).

### 8. DOT graph export (for visualizers)

For a quick **graph visualization**, you can export the compiled IR as a DOT file and use Graphviz or similar tools:

```bash
python scripts/render_graph.py examples/status_branching.ainl > status_branching.dot
dot -Tpng status_branching.dot -o status_branching.png
```

This helper:

- compiles the program to graph IR (optionally strict),
- renders a minimal DOT graph with:
  - one subgraph per label (`L1`, `L2`, ...),
  - one node per IR node (labeled by op and adapter prefix, e.g. `R (http)`),
  - edges labeled by their `port` (`next`, `then`, `else`, etc.).

You can also feed it an existing IR JSON file instead of source:

```bash
python scripts/render_graph.py tests/emits/server/ir.json --from-ir > server.dot
```

`scripts/render_graph.py` is a thin, read-only visualization helper; it does **not** change any compiler or runtime semantics.
