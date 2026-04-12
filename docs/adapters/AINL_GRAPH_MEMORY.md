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
| `memory_search` | `query`, `node_type`, `agent_id`, `limit` | `{"results": [...], "count": N}` — substring match over label + JSON payload + tags; `node_type` / `agent_id` filter when non-empty |
| `export_graph` | (none) | `{"nodes": [...], "edges": [...]}` |

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

**Capabilities:** IR that contains these ops (legacy `steps` or label **graph** `nodes`) contributes **`ainl_graph_memory`** to fallback adapter inference (`_fallback_adapters_from_label_steps`) when AVM metadata is missing. Programs still need **`capabilities.allow`** (or execution requirements) to include **`ainl_graph_memory`** and a **registered** adapter instance — otherwise dispatch raises `AdapterError` / blocked adapter behavior.

**Tests:** `tests/test_memory_recall_op.py` — call shapes, step vs graph mode, missing adapter.

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

## Demo

`demo/procedural_roundtrip_demo.py` — two-agent procedural round-trip using real OpenRouter when configured; uses **`memory_store_pattern`** so recall returns **`payload.steps`**.

## Related bridge code

- **`armaraos/bridge/bridge_token_budget_adapter.py`** — token budget / TTL tuner subprocess bridge; top-of-file docstring explains **importlib** loading (avoids circular imports when the module name is `bridge_token_budget_adapter`).

## See also

- [`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md) — SQLite **`memory`** adapter contract
- [`../ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md) — ArmaraOS host pack + env table
- [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md) — runtime vs compiler ownership
- OpenClaw bridge table (different tree): [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md)
