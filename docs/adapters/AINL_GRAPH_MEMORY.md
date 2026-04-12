# AINL graph memory (`ainl_graph_memory`)

JSON-backed **node/edge graph memory** for the **ArmaraOS ↔ AINL bridge**: episodic, semantic, procedural, and persona-shaped nodes with typed edges. This is **not** the SQLite **`memory`** adapter ([`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md)); it is a separate adapter name and persistence format used when graphs need a lightweight, file-local knowledge graph.

## Layout and persistence

| Item | Detail |
|------|--------|
| **Module** | `armaraos/bridge/ainl_graph_memory.py` (ArmaraOS integration layer; lives under this repo’s `armaraos/bridge/` tree, not `adapters/` core) |
| **Default file** | `~/.armaraos/ainl_graph_memory.json` |
| **Override** | `AINL_GRAPH_MEMORY_PATH` → absolute or `~`-expanded path to the JSON store |
| **Logger** | `ainl.graph_memory` (`logging.getLogger("ainl.graph_memory")`) |
| **On-disk shape** | `{"nodes": [...], "edges": [...]}` — see `MemoryNode` / `MemoryEdge` in the module for fields |

`GraphStore` loads the file at construction, prunes TTL-expired nodes, and writes atomically via a `.tmp` file + `os.replace`.

**Dry run:** respects `frame["dry_run"]` / truthy variants and `AINL_DRY_RUN` (same convention as other bridge adapters).

## Runtime adapter: `AINLGraphMemoryBridge`

Registered under the canonical adapter name **`ainl_graph_memory`**. Dispatch is via `RuntimeAdapter.call(target, args, context)`:

| Verb (`target`) | Args | Returns (typical) |
|-----------------|------|-------------------|
| `memory_store_pattern` | `label`, `steps` (list of dicts), `agent_id`, `tags` (list) | `{"node_id", "step_count"}` — root procedural node’s `payload` includes **`steps`** for downstream recall |
| `memory_recall` | `node_id` | Full node dict, or `{"error": "not found"}` |
| `memory_search` | `query`, `node_type`, `agent_id`, `limit` | `{"results": [...], "count": N}` — substring match over label + JSON payload + tags; `node_type` / `agent_id` filter when non-empty. Among matches, order follows **insertion order** in the store (no relevance scoring). **`count`** is **`len(results)`** after applying **`limit`**. |
| `export_graph` | (none) | `{"nodes": [...], "edges": [...]}` |
| `persona_update` | dict: `trait_name`, `strength`, `learned_from` (list), optional `edge_type` | `{"ok", "node_id", ...}` — upserts persona trait node; **`edge_type`** must be a valid **`EdgeType`** string when provided |
| `persona_get` | dict: `trait_name` | Trait payload or error |
| `persona_load` | (none) | `{"traits": [...], "persona_context": {...}}` — used for frame injection after load |

**Python hooks** (used by the bridge runner and demos, not IR ops): `boot`, `on_delegation`, `on_tool_execution`, `on_prompt_compress`, `on_swarm_message`, `on_persona_update`.

### Example `R` lines (when the adapter is allowed + registered)

```text
R ainl_graph_memory memory_recall "nid_abc" ->recalled
R ainl_graph_memory memory_search "transformer" "procedural" "" 5 ->hits
```

Use frame variables for dynamic ids/queries; follow normal strict dataflow rules for quoted vs bare tokens.

## Engine IR ops: `MemoryRecall` and `MemorySearch`

`RuntimeEngine` (`runtime/engine.py`) treats these like **`CacheGet` / `CacheSet`**: shared handling in **`_exec_step`** (step mode and async graph `else` path) plus explicit branches in sync **`_run_label_graph`** for trace + linear graph advance.

| Op | Step / node fields | Runtime dispatch |
|----|--------------------|------------------|
| **MemoryRecall** | `node_id` (resolved), `out` (default `recalled`) | `adapters.call("ainl_graph_memory", "memory_recall", [node_id], call_ctx)` |
| **MemorySearch** | `query` (resolved string), optional `node_type`, optional `agent_id`, `limit` (default `10`), `out` (default `results`) | `adapters.call("ainl_graph_memory", "memory_search", [query, node_type, agent_id, limit], call_ctx)` |

`call_ctx` is the frame plus `_runtime_async`, `_observability`, `_adapter_registry` (same enrichment as `R` adapter calls).

**Capabilities:** IR that contains these ops (legacy `steps` or label **graph** `nodes`) contributes **`ainl_graph_memory`** to fallback adapter inference (`_fallback_adapters_from_label_steps`) when AVM metadata is missing. Programs still need **`capabilities.allow`** (or execution requirements) to include **`ainl_graph_memory`** and a **registered** adapter instance — otherwise the engine surfaces a structured **`AinlRuntimeError`** (message includes missing / blocked adapter details; same pattern as other adapter failures wrapped from **`AdapterError`**). Steps **`persona.update`** / **`memory.merge`** participate in the same inference path for **`ainl_graph_memory`** / **`memory`** respectively; see **`MEMORY_CONTRACT.md`** §3.7 for merge-specific SQLite requirements.

**Tests:** `tests/test_memory_recall_op.py` — **`MemoryRecall`** / **`MemorySearch`** dispatch shapes, step vs graph mode, missing adapter (mock bridge). **`tests/test_memory_search_op.py`** — **`MemorySearch`** against a temp-backed **`GraphStore`** (matches, empty results, special characters in **`query`**, **`limit`** cap, insertion-order “ranking”, structured error when **`ainl_graph_memory`** is not registered).

## Typed edges (`EdgeType`), confidence, and contradictions

`armaraos/bridge/ainl_graph_memory.py` defines **`EdgeType`** on graph edges (string enum values persisted in JSON):

| Kind | `EdgeType` value | Typical use |
|------|------------------|---------------|
| Structural | `caused_by`, `part_of`, `references`, `derived_from`, `inherited_by` | Causality, containment, derivation |
| Epistemic | `knows`, `believes`, `learned_from`, `contradicts` | Agent–concept knowledge, uncertain belief, provenance, conflicting claims |

**`MemoryEdge`** includes **`confidence: float`** (default **`1.0`**). For **`believes`**, `GraphStore.add_edge` reads optional **`meta["confidence"]`** on the edge and stores it on the returned **`MemoryEdge`**.

**`MemoryNode`** includes **`contradicted_by: list[str]`** (peer node ids). For **`contradicts`** edges, **`GraphStore.add_edge`**:

- sets **`has_contradiction: True`** inside each endpoint’s **`payload["metadata"]`** (merged with existing metadata),
- appends the opposite node id to **`contradicted_by`** on each side **once** (duplicate **`add_edge`** calls with the same edge id do not duplicate list entries).

Unsupported **`edge_type`** strings raise **`AdapterError`** from **`add_edge`**.

## Compiler / IR: `persona.update` and bridge `persona_update`

AINL sources may use a **standalone label step** (not an `R` line):

```text
persona.update curiosity 0.8
persona.update curiosity 0.8 episode_node_7 learned_from
persona.update curiosity 0.8 learned_from
```

Slots: **trait name** (string), **strength** (float), optional **learned_from** episode id(s), optional **`edge_type`** token (must be a member of **`EdgeType`** / compiler **`EDGE_TYPE_TOKENS`** in `compiler_v2.py`). The compiler emits a step with **`op`: `persona.update`**, **`trait_name`**, **`strength`**, **`learned_from`**, and optional **`edge_type`**.

**Runtime:** `RuntimeEngine` dispatches **`persona.update`** to **`adapters.call("ainl_graph_memory", "persona_update", [kw], call_ctx)`** with the resolved fields. **`AINLGraphMemoryBridge.persona_update`** upserts **`MemoryNode`** rows with **`node_type="persona"`** and links traits to the active **`agent_id`** using **`GraphStore`** (default edge kinds include **`part_of`** for structural links; epistemic kinds come from **`edge_type`** when set).

**Tests:** `tests/test_semantic_edges.py` (graph store behavior + grammar token class + compile emits **`edge_type`**).

## MemoryMerge vs graph recall (SQLite `memory` adapter)

- **`MemoryRecall`** / **`MemorySearch`** (this doc, **`ainl_graph_memory`**): load or search **nodes** in the **JSON graph file** — handy for episodic/semantic/procedural **records** as first-class graph vertices.
- **`memory.merge`** / **`MemoryMerge`** (**SQLite `memory` adapter** + **`RuntimeEngine`**): load a **named procedural IR fragment** (`labels` + `legacy.steps`) from table **`ainl_memory_patterns`**, **merge** it into the **current program’s** live **`labels`** map under fresh **`_mm_*`** ids, **run** that subgraph, and bind the **`J`** result to a variable. See **[`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md)** §3.7.

Use **graph recall** when you need a **blob of graph JSON**. Use **MemoryMerge** when you want **executable IR** stitched back into the same run.

## ArmaraOS bridge runner

`armaraos/bridge/runner.py`:

- **`ainl_graph_memory`** is in **`_REQUIRED_ADAPTERS`** and **`build_wrapper_registry()`** registers `AINLGraphMemoryBridge`, calls **`boot()`** once, and keeps a module-level reference for post-run hooks.
- After a successful wrapper run, **`on_delegation(...)`** records an episodic delegation node (wrapper name, dry-run flag, truncated output preview).

Entry: `python3 armaraos/bridge/runner.py <wrapper> [--dry-run] [--trace]` (see module docstring). Shims may live under `scripts/` for backwards compatibility.

## Optional graph browser

`armaraos/bridge/graph_viz/` — D3 HTML UI + small FastAPI app:

- **`GET /`** — serves `memory_graph.html`
- **`GET /api/memory/graph`** — JSON from `GraphStore.export_graph()`; optional query **`src`** = path to another `.json` graph file

Run (from repo root so imports resolve):

```bash
cd /path/to/AI_Native_Lang
PYTHONPATH=. uvicorn armaraos.bridge.graph_viz.server:app --reload --port 8765
```

## Demos

- **`demo/procedural_roundtrip_demo.py`** — two-agent procedural round-trip using real OpenRouter when configured; uses **`memory_store_pattern`** so recall returns **`payload.steps`**.
- **`demo/ainl_graph_memory_demo.py`** — self-contained Python walkthrough (episodic, semantic, procedural, persona nodes; graph walk + **`ainl_graph_memory_export.json`** under **`demo/`**). Run from repo root: **`python3 demo/ainl_graph_memory_demo.py`**. Export path is gitignored.

## Related bridge code

- **`armaraos/bridge/bridge_token_budget_adapter.py`** — token budget / TTL tuner subprocess bridge; top-of-file docstring explains **importlib** loading (avoids circular imports when the module name is `bridge_token_budget_adapter`).

## See also

- [`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md) — SQLite **`memory`** adapter contract
- [`../ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md) — ArmaraOS host pack + env table
- [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md) — runtime vs compiler ownership
- OpenClaw bridge table (different tree): [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md)
