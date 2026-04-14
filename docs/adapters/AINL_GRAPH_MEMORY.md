---
title: AINL graph memory (`ainl_graph_memory`)
description: >-
  JSON-backed node/edge graph memory for the ArmaraOS ↔ AINL bridge (episodic,
  semantic, procedural, persona). Distinct from the SQLite memory adapter; see
  MEMORY_CONTRACT.md for the memory adapter contract.
---

# AINL graph memory (`ainl_graph_memory`)

JSON-backed **node/edge graph memory** for the **ArmaraOS ↔ AINL bridge**: episodic, semantic, procedural, and persona-shaped nodes with typed edges. This is **not** the SQLite **`memory`** adapter ([`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md)); it is a separate adapter name and persistence format used when graphs need a lightweight, file-local knowledge graph.

## Further reading

- **Narrative (ecosystem):** [When Your AI Agent Actually Remembers: Introducing AINL’s Graph-as-Memory Architecture](https://ainativelang.com/blog/graph-as-memory-architecture-ainl) — public overview of unified graph-as-memory in Python (AINL) and Rust (`ainl-*`, ArmaraOS).
- **Chronology and prior-art framing:** [`PRIOR_ART.md`](https://github.com/sbhooley/ainativelang/blob/main/PRIOR_ART.md) in the AINL repository (timeline table + citations). Same document is mirrored under **ArmaraOS** as [`PRIOR_ART.md`](https://github.com/sbhooley/armaraos/blob/main/PRIOR_ART.md).

## Layout and persistence

| Item | Detail |
|------|--------|
| **Module** | `armaraos/bridge/ainl_graph_memory.py` (ArmaraOS integration layer; lives under this repo’s `armaraos/bridge/` tree, not `adapters/` core) |
| **Default file** | `~/.armaraos/ainl_graph_memory.json` |
| **Override** | `AINL_GRAPH_MEMORY_PATH` → absolute or `~`-expanded path to the JSON store |
| **Logger** | `ainl.graph_memory` (`logging.getLogger("ainl.graph_memory")`) |
| **On-disk shape** | `{"nodes": [...], "edges": [...]}` — see `MemoryNode` / `MemoryEdge` in the module for fields |

### Reading the authoritative Rust store (ArmaraOS)

Dashboard chat persists graph memory to **SQLite** at `~/.armaraos/agents/{uuid}/ainl_memory.db` (or under **`ARMARAOS_HOME`** / **`OPENFANG_HOME`**) via Rust **`GraphMemoryWriter`**. The Python **`GraphStore`** can **hydrate from a JSON export of that DB** so **`ainl run`** graphs see the same nodes without a second writer.

**Manual export (one-off / CI):** `openfang memory graph-export <agent-uuid> --output /path/to/snapshot.json` (uses **`GraphMemoryWriter::export_graph_json_for_agent`**; same shape as **`AgentGraphSnapshot`**). Point Python at that file with **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** set to the **`.json` file path** (see *Resolution rules* below), or copy the file and pass a path that ends in **`.json`**.

**Merge order:** on construction, **`GraphStore._load`** merges the resolved ArmaraOS snapshot **first**, then overlays the JSON file at **`AINL_GRAPH_MEMORY_PATH`** (same node **`id`** in the JSON file overwrites the export copy).

Correlation fields on exported nodes include **`agent_id`** on every row; orchestration **`trace_id`** is attached on episodic **`trace_event`** JSON and as semantic fact tags (`trace_id:…`) when the turn had an orchestration context.

**Rust-written `tags` on episodes:** the ArmaraOS daemon may also populate episodic **`tags`** (and extend semantic **`tags`**) with deterministic **`ainl-semantic-tagger`** strings when the binary is built with **`ainl-tagger`** and the process sets **`AINL_TAGGER_ENABLED=1`** (exactly that literal). Export / Python hydration then sees the same `tags` arrays as on inbox-imported nodes. See **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) (*Optional extraction and tagging*).

#### Env: **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** + **`ARMARAOS_AGENT_ID`**

| Layer | Behavior |
|-------|------------|
| **Rust auto-refresh** (**`openfang-runtime`**, post–persona evolution) | If **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** is set to a **non-empty string**, it names a **writable directory only**: the daemon writes **`{dir}/{agent_id}_graph_export.json`** (per chat agent). Parent directories are created as needed. If the variable is **unset**, Rust writes **`{openfang_home_dir()}/agents/{agent_id}/ainl_graph_memory_export.json`** (same home resolution as **`ainl_memory.db`** — **`ARMARAOS_HOME`**, **`OPENFANG_HOME`**, then **`~/.armaraos`** vs **`~/.openfang`**). Resolution helper: **`armaraos_graph_memory_export_json_path`** in **`crates/openfang-runtime/src/graph_memory_writer.rs`**. |
| **Python cold load** (**`_armaraos_export_snapshot_path`** in this module) | **Directory mode:** path **exists as a directory**, *or* its final component’s name does **not** end with **`.json`** (case-insensitive) → snapshot file is **`{that path}/{ARMARAOS_AGENT_ID}_graph_export.json`**. **`ARMARAOS_AGENT_ID`** is **required** in this mode; if it is missing, the bridge logs a warning and **skips** the snapshot merge. **File mode:** path looks like a single **`.json`** file (per the rule above) and is used **as-is** — backward compatible with older single-agent setups and CLI exports. **No export env:** if **`ARMARAOS_AGENT_ID`** is set, Python also tries **`{openfang_home}/agents/{id}/ainl_graph_memory_export.json`** (same **`_armaraos_openfang_home()`** order as Rust). |

**Operator migration (Rust):** older installs pointed **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** at a **single file**; the daemon now always treats the value as a **directory** and appends **`/{agent_id}_graph_export.json`**. Point the variable at the **parent directory** of the old file (or unset it and rely on the default **`ainl_graph_memory_export.json`** next to SQLite). Python **file mode** still accepts a concrete **`.json`** path for reads.

**Auto-refresh summary:** after each chat turn’s persona evolution pass, **openfang-runtime** rewrites the resolved per-agent JSON path so long-lived Python processes can re-read it without running **`openfang memory graph-export`** manually (Python still treats that JSON as read-only input unless it writes the separate **`AINL_GRAPH_MEMORY_PATH`** store).

`GraphStore` loads the snapshot at construction, prunes TTL-expired nodes, and writes the main graph file atomically via a `.tmp` file + `os.replace`.

**Dry run:** respects `frame["dry_run"]` / truthy variants and `AINL_DRY_RUN` (same convention as other bridge adapters).

**Inbox write-back:** when **`ARMARAOS_AGENT_ID`** is set and **`<home>/agents`** exists, **`AINLGraphMemoryBridge`** and the bridge runner can append rows to **`ainl_graph_memory_inbox.json`** (see **Python inbox** below and **`armaraos/docs/graph-memory-sync.md`**).

## Python inbox (`AinlMemorySyncWriter` → Rust `ainl_memory.db`)

When the ArmaraOS host (or any wrapper) exports **`ARMARAOS_AGENT_ID`**, Python code can **append** graph rows for the daemon to ingest into per-agent SQLite without calling `openfang` from Python.

| Item | Detail |
|------|--------|
| **Module** | `armaraos/bridge/ainl_memory_sync.py` — class **`AinlMemorySyncWriter`** |
| **On-disk file** | **`<home>/agents/<ARMARAOS_AGENT_ID>/ainl_graph_memory_inbox.json`** where **`<home>`** is **`ARMARAOS_HOME`**, else **`OPENFANG_HOME`**, else **`~/.armaraos`** if that directory exists else **`~/.openfang`** (same order as **`ainl_memory_sync`**) |
| **Activation** | **`ARMARAOS_AGENT_ID`** set and `agents/` directory exists under the resolved home; otherwise **`is_available()`** is false and **`push_nodes`** / **`push_patch`** no-op with **`sync_unavailable`**. |
| **Envelope** | JSON object with **`nodes`** (list of **`MemoryNode`**-shaped dicts), **`edges`** (list; preserved across appends), optional **`schema_version`** (default **`"1"`**), optional **`source_features`** (strings). **`push_nodes`** merges **`DEFAULT_SOURCE_FEATURES`** (`ainl_graph_memory`, `inbox_v1`) into **`source_features`**. |
| **Tagger policy** | Callers that emit tagger-heavy **semantic** nodes should add the literal string **`requires_ainl_tagger`** to **`source_features`** (Python constant **`REQUIRES_AINL_TAGGER`**). A Rust binary built **without** the **`ainl-tagger`** feature skips **semantic** inbox rows that have **non-empty `tags`** when that marker is present (see **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md)). |
| **Schema contract** | **`armaraos/bridge/ainl_graph_memory_inbox_schema_v1.json`** — versioned envelope for tooling and CI. |
| **CI** | **`.github/workflows/cross-repo-armaraos-bridge.yml`** — validates the schema JSON parses and **`cargo build -p openfang-runtime --lib`** against public **sbhooley/armaraos** so inbox-related Rust stays in sync. |
| **Host drain** | **`GraphMemoryWriter::drain_python_graph_memory_inbox`** → **`openfang_runtime::ainl_inbox_reader::drain_inbox`** (per-agent SQLite). **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md). |

**Typical Python producers:** the graph-memory bridge may push episodic **boot** rows after **`boot()`**, **persona** rows after **`persona_update()`**, and **patch** rows after **`memory_patch()`** flush when sync is available; **`armaraos/bridge/runner.py`** can record **non-core** adapter calls via **`on_tool_execution`** into the same inbox path when **`ARMARAOS_AGENT_ID`** is set.

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

### `boot()`, `AINL_BUNDLE_PATH`, and ArmaraOS scheduled `ainl run`

When **`AINLGraphMemoryBridge.boot(agent_id=…)`** runs, it sets the active agent id, then **best-effort** loads a host-provided bundle:

| Env | When set | Behavior |
|-----|----------|----------|
| **`AINL_BUNDLE_PATH`** | Absolute path to an existing **`.ainlbundle`** file (ArmaraOS sets this on the **`ainl run`** child when `~/.armaraos/agents/<agent_id>/bundle.ainlbundle` exists) | `AINLBundle.load(path)` then: (1) **`persona`** — for each dict in **`bundle.persona`**, call **`persona.update`** (per-row errors are skipped). (2) **`memory`** — for each dict in **`bundle.memory`**, normalize to a **`MemoryNode`** and **`write_node`** only when the node **`id` is not already** in the live JSON **`GraphStore`** (episodic, semantic, procedural, **`patch`**; **`persona`** rows in **`memory`** are ignored so **`bundle.persona`** stays the sole persona bootstrap path). Malformed rows, unknown **`node_type`**, or load failures are **non-fatal**. Boot logs counts when the bundle file was read successfully. |
| **`AINL_AGENT_ID`** | Set with the bundle path by the host | Carried for host/debug alignment; bridge behavior is driven by the **`agent_id`** argument to **`boot`**. |

**Bundle `memory` rows** are the same shape as **`AINLBundleBuilder._snapshot_memory()`** / **`export_graph()`** node dicts (non-persona only in the snapshot). The live store **wins** on **`id`** collisions: bundle pre-seed is bootstrap state, not authority over runtime writes.

After a successful scheduled graph, the ArmaraOS kernel runs a **background** Python export that calls **`boot`** again and **`AINLBundleBuilder.build(..., bridge).save(...)`** so the next cron tick sees updated **persona** and **memory** snapshots in the bundle file. Details: **ArmaraOS** [`docs/scheduled-ainl.md`](https://github.com/sbhooley/armaraos/blob/main/docs/scheduled-ainl.md) (*AINL bundle + graph memory*), bundle schema: **`runtime/ainl_bundle.py`**, tests: **`tests/test_ainl_bundle.py`** (`test_bundle_boot_*`, `test_bundle_round_trip_preserves_non_persona_memory`).

**Not the same store:** ArmaraOS dashboard chat uses Rust **`ainl-memory`** SQLite at **`~/.armaraos/agents/<id>/ainl_memory.db`** (**`GraphMemoryWriter`**) to query **Persona** nodes and append **`[Persona traits active: …]`** to the **system prompt** after orchestration context (strength ≥ **0.1**, rolling **90**-day window). That path never reads **`AINL_BUNDLE_PATH`**; it is separate from this JSON **`ainl_graph_memory`** file used inside **`ainl run`**. See **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md).

### Example `R` lines (when the adapter is allowed + registered)

```text
R ainl_graph_memory memory_recall "nid_abc" ->recalled
R ainl_graph_memory memory_search "transformer" "procedural" "" 5 ->hits
```

Use frame variables for dynamic ids/queries; follow normal strict dataflow rules for quoted vs bare tokens.

### Dotted `memory.*` / `persona.*` on `R` (compiler sugar → same bridge)

When **`ainl_graph_memory`** is allowed and registered, **`RuntimeEngine`** also accepts **dotted** adapter verbs on **`R`** lines (single token after **`R`**). They compile to graph nodes whose **`data.adapter`** is the dotted name and optional IR field **`memory_type`** (for introspection — see **`../reference/GRAPH_SCHEMA.md`**).

| Source (`R …`) | Bridge target (typical) | Notes |
|----------------|-------------------------|--------|
| `memory.recall` | `memory_recall` | Load one node by id. |
| `memory.search` | `memory_search` | Substring search + filters. |
| `memory.export_graph` / `memory.export` | `export_graph` | Full JSON snapshot. |
| `memory.store_pattern` / `memory.store` | `memory_store_pattern` | Persist procedural steps; you may pass one frame dict `{"pattern_name", "steps"}`. |
| `memory.pattern_recall` | `memory_pattern_recall` | Load named pattern **`steps`** into the frame and set **`__last_pattern__`** for **`memory.merge`**. |
| `persona.load` / `persona.get` / `persona.update` | `persona_load` / `persona_get` / `persona_update` | Persona bundle ops (**`persona.update`** also exists as a standalone label step — see below). |

**Typical `pattern_recall` → `merge` (SQLite procedural executor):**

```text
R memory.pattern_recall my_pattern ->steps
R memory.merge steps ->merged_result
```

**Not the same path:** split-token **`R memory store_pattern …`** / **`R memory recall_pattern …`** targets the **SQLite** **`memory`** adapter (see **`MEMORY_CONTRACT.md`** §3.7), not this JSON graph file.

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

`armaraos/bridge/runner.py` is the canonical host for scheduled **wrapper** `.ainl` graphs (OpenRouter + CRM/GitHub + memory surfaces). Registry wiring is **shared** with other Python hosts via **`adapters/armaraos_integration.py`**:

| Step | What runs |
|------|-----------|
| Base registry | **`build_armaraos_monitor_registry(boot_graph_memory=False)`** — **`allow` + `register`** for **`ainl_graph_memory`**, **`bridge`** (token-budget / rolling JSON helpers), and **`cron_drift_check`** (**`CronDriftCheckAdapter`** → **`run_report()`**). Names are listed in **`ARMARAOS_MONITOR_PRESEEDED_ADAPTERS`** (`adapters/armaraos_defaults.py`). |
| Host adapters | **`build_wrapper_registry()`** then **`allow`/`register`** for **`armaraos_memory`**, **`github`**, **`crm`**, **`armaraos_token_tracker`**. |
| Graph bootstrap | **`boot_armaraos_graph_memory(reg, agent_id=…)`** — uses **`AdapterRegistry.get("ainl_graph_memory")`**, asserts **`AINLGraphMemoryBridge`**, calls **`boot()`**. Module global **`_GRAPH_MEMORY_BRIDGE`** keeps the same instance for **`on_delegation`** and runner inbox tracing. |
| Registry return | **`_GraphToolInboxAdapterRegistry(inner)`** — delegates **`call`/`call_async`** to **`inner`**, then **`on_tool_execution`** + **`_sync.push_nodes`** for adapter names other than **`core`**, **`ainl_graph_memory`**, **`bridge`** (when inbox sync **`is_available()`** and not dry-run). |
| Grant gate | Import-time check: **`_REQUIRED_ADAPTERS`** must be allowed when **`ARMARAOS_SECURITY_PROFILE`** narrows the grant (**`cron_drift_check`** is pre-seeded but not currently in that required set). |

After a successful wrapper run, **`on_delegation(...)`** records an episodic delegation node (wrapper name, dry-run flag, truncated output preview).

**Capability contract:** pre-seeded adapters are already on the registry **`_allowed`** set; hosts only add capabilities for *extra* adapters. Intersection with a restrictive profile still works the usual way (narrower **`allowed_adapters`**).

Entry: `python3 armaraos/bridge/runner.py <wrapper> [--dry-run] [--trace]` (see module docstring). Shims may live under `scripts/` for backwards compatibility.

**Tests:** **`tests/test_armaraos_monitor_registry.py`** (pre-seed, public **`get`**, boot path, repeated boot on same registry, runner source must not reference **`reg._adapters`** in **`build_wrapper_registry`**). **`armaraos/bridge/tests/test_ainl_memory_sync.py`** (inbox JSON, unavailable env, concurrent atomic writes).

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

- **`adapters/armaraos_integration.py`** — **`build_armaraos_monitor_registry`**, **`boot_armaraos_graph_memory`**, **`armaraos_monitor_registry()`** (seed without immediate graph **`boot`**). Prefer these entrypoints over re-implementing allow/register lists.
- **`armaraos/bridge/cron_drift_check.py`** — CLI drift report plus **`CronDriftCheckAdapter`** (**`R cron_drift_check report`** → **`run_report()`**).
- **`armaraos/bridge/bridge_token_budget_adapter.py`** — shim to **`openclaw/bridge/bridge_token_budget_adapter.py`**; top-of-file docstring explains **importlib** loading (avoids circular imports when the module name is `bridge_token_budget_adapter`).

## See also

- [`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md) — SQLite **`memory`** adapter contract
- **`armaraos/bridge/ainl_memory_sync.py`** — inbox writer (**`AinlMemorySyncWriter`**, **`push_nodes`** / **`push_patch`**)
- [`../../armaraos/docs/graph-memory-sync.md`](../../armaraos/docs/graph-memory-sync.md) — inbox triggers, envelope, env (**`ARMARAOS_AGENT_ID`**), tests + CI (vendored copy; upstream **armaraos** keeps the same file under **`docs/`**)
- **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) — daemon **`GraphMemoryWriter`**, **`ainl_graph_memory_inbox.json`** drain (**`ARMARAOS_AGENT_ID`**)
- [`../ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md) — ArmaraOS host pack + env table (**`openfang_runtime_ainl`** on **`GET /api/status`**)
- [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md) — runtime vs compiler ownership
- OpenClaw bridge table (different tree): [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md)
