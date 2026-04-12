# Agent Graph v1 Schema

This document defines the canonical graph shape that agents and tooling can rely on for query, diff, and rewrite. The runtime treats **node** (top-level) fields as canonical; **node.data** is the op payload / raw compiler output.
Cross-reference map:

- IR overview: `IR_SCHEMA.md`
- Runtime/compiler ownership: `../RUNTIME_COMPILER_CONTRACT.md#source-of-truth`
- Graph execution policy: `../RUNTIME_COMPILER_CONTRACT.md#graph-vs-legacy-steps-execution-policy`
- Conformance state: `../CONFORMANCE.md#ir-mode-10-alignment`

## Node schema

Every node has:

| Field     | Type           | Required | Description |
|----------|----------------|----------|-------------|
| `id`     | string         | yes      | Canonical id `n1`, `n2`, ... (contiguous per label). |
| `op`     | string         | yes      | Core op: `R`, `If`, `Call`, `Loop`, `While`, `J`, `Retry`, `Err`, `Set`, `X`, `Filt`, `Sort`, `CacheGet`, `CacheSet`, `QueuePut`, `Tx`, `Enf`. |
| `effect` | `"io" \| "pure" \| "meta"` | yes | `io` = side effects (R, Call, CacheSet, QueuePut, Tx); `pure` = rest; `meta` = Err, Retry. |
| `reads`  | list[string]   | yes      | Frame keys read (best-effort static). |
| `writes` | list[string]   | yes      | Frame keys written. |
| `lineno` | int \| null   | no       | Source line for tooling. |
| `data`   | object         | yes      | Legacy step dict (op payload); runtime reads `n.get("data")` for execution. |
| `memory_type` | string   | no       | Present on **`R`** nodes when `data.adapter` is a graph-memory / persona dotted verb (`memory.recall` → **`episode`**, `memory.search` → **`semantic`**, `memory.store_pattern` / `memory.store` → **`procedural`**, `memory.export_graph` / `memory.export` → **`episode`**, `memory.pattern_recall` → **`procedural`**, `persona.{load,get,update}` → **`persona`**). Omitted for other ops. |

**Design:** Agents use `node.op`, `node.effect`, `node.reads`, `node.writes`, `node.lineno` for analysis. They do not need to parse deep into `data` for basics. Optional **`memory_type`** supports tiered introspection without parsing `data.adapter`.

Optional (future): `types: { var: "Any" | "List" | ... }`.

## Edge schema

Every edge has:

| Field     | Type                | Required | Description |
|----------|---------------------|----------|-------------|
| `from`   | string              | yes      | Source node id. |
| `to`     | string              | yes      | Target node id or label id. |
| `to_kind`| `"node" \| "label"` | yes      | Whether `to` is a node or a label. |
| `port`   | string              | yes      | Branch kind; see below. |

**Ports:**

- **Linear:** `next` - normal successor node.
- **Branch:** `then` / `else` (If); `body` / `after` (Loop, While).
- **Error/retry:** `err`, `retry` (node edges); `handler` (label edge from Err node).

**`labels[label_id].emit_edges`** (separate from **`edges`**, additive IR):

- **`port: "data"`** — producer **`R` / `Set`** node → linear **`next`** successor; includes **`var`** (frame key written by that step).
- **`port: "emit"`** — exit **`J`** node → literal **`to: "emit_target"`**; includes **`var`** (return var) and **`target`** (emit platform name from **`ir["required_emit_targets"]["minimal_emit"]`** after compile-time stub fallback).
- **Targeting contract:** explicit `Err @nX` / `Retry @nX` in source must lower to edges whose `from` is that exact canonical node id.

When a single node-successor exists and `port` is missing, normalizers may default `port` to `"next"` for backward compatibility. After full normalization, **every edge must have `port`**; linear successor must be `port=\"next\"` only.

## Label graph shape

Per label:

- **nodes**: list of nodes (canonical ids, no gaps).
- **edges**: list of edges (control-flow only).
- **emit_edges**: list of data-flow + emit-routing edges (see ports above); may be empty on older IR.
- **entry**: node id of the single entry.
- **exits**: list of `{ node, var }` for each `J` node.

## Legacy augmentation

Older IR may lack `effect`/`reads`/`writes`/`lineno` on nodes or `port` on edges. Use **`tooling.graph_normalize.normalize_graph(ir)`** to produce a copy with:

- Missing node `effect`/`reads`/`writes` computed from `node.data` heuristics.
- Missing edge `port` defaulted (e.g. `"next"` for single linear successor).

So legacy IR still runs; normalization makes it query-safe without breaking existing behavior.

## Validation (phases)

**Phase 1 (current):** Every node has `id`, `op`; `data.op` matches node `op` (or exists). Every edge has `from`, `to`, `to_kind`; if multiple node-successors exist, at least one must have `port="next"` (or legacy single-edge behavior behind a flag).

**Phase 2 (strict):** Every edge has `port`; linear successor is `port="next"` only; op-specific ports (If: then/else; Loop: body/after; executable nodes: optional retry/err where modeled by compiler/runtime contract).

## Query surface

Use **`tooling.graph_api`** for deterministic answers:

- `label_nodes`, `label_edges` (each accepts a **single** label id or a **sequence** of ids — merged list / dict)
- `emit_edges`, `data_flow_edges` (`port=="data"` subset), `memory_nodes` (nodes with **`memory_type`**, optional filter)
- `successors`, `predecessors`
- `io_nodes(label)`, `nodes_using_adapter(label, adapter_prefix)`
- `error_paths(label, from_node=None)`, `exit_nodes(label)`

**Human-readable diagrams:** `ainl visualize` / `ainl-visualize` / `scripts/visualize_ainl.py` render **Mermaid** from the same `labels` graph (strict compile). See `docs/architecture/GRAPH_INTROSPECTION.md` §7 and the root `README.md` (*Visualize your workflow*).

## Rewrites and diff

- **Rewrites:** Clone IR -> apply change -> run validation -> return `{ ok: True, ir }` or `{ ok: False, error }`. Helpers: `insert_node_after`, `rewire_edge`, `wrap_r_with_retry`, `attach_err_handler`.
- **Diff:** `tooling.graph_diff.graph_diff(old_ir, new_ir)` - nodes added/removed/changed, edges added/removed/rewired; human summary + machine JSON.

---

## Agent Guidance (all model sizes)

- Prefer `node.op`, `effect`, `reads`, `writes`, and `edges.port` for reasoning before inspecting raw `data`.
- Treat `legacy.steps` as compatibility serialization; graph nodes/edges are canonical for analysis and execution.
- When generating patches, preserve canonical node-id forms (`n<number>`) and explicit edge ports.
