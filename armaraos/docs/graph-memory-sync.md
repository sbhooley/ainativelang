# Graph memory inbox sync (Python → ArmaraOS)

Python **`ainl_graph_memory`** persists to a JSON **`GraphStore`** and can **read** the Rust-exported snapshot (`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT` / **`ainl_graph_memory_export.json`**). Mutations from Python do not open **`ainl_memory.db`** directly. **`armaraos.bridge.ainl_memory_sync.AinlMemorySyncWriter`** **appends** **`MemoryNode`** dicts into **`ainl_graph_memory_inbox.json`** so ArmaraOS can merge them into SQLite (see **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) — **`GraphMemoryWriter::drain_python_graph_memory_inbox`**).

## When rows are pushed

| Source | Trigger |
|--------|---------|
| **`AINLGraphMemoryBridge.boot()`** | After the episodic **bridge_boot** node is persisted (non–dry-run). |
| **`AINLGraphMemoryBridge.persona_update()`** | After **`GraphStore.write_node`** for the persona node (non–dry-run). |
| **`AINLGraphMemoryBridge.memory_patch()`** | After **`GraphStore.flush()`** following a successful GraphPatch (non–dry-run). |
| **`armaraos/bridge/runner.py`** | **`_GraphToolInboxAdapterRegistry`** wraps **`AdapterRegistry`**: after **`core`**, **`ainl_graph_memory`**, and **`bridge`** calls are excluded, runs **`on_tool_execution`** then **`push_nodes`** when **`is_available()`**. Skips **`dry_run`** in context and **`AINL_DRY_RUN`**. |

Other entrypoints (plain **`ainl run`**, MCP) use the bridge hooks above only; they do not install the runner wrapper unless the host wires it.

## Environment variables

| Variable | Role |
|----------|------|
| **`ARMARAOS_AGENT_ID`** | **Required** for sync. Selects **`agents/<id>/`**. Unset → **`SyncResult(error="sync_unavailable")`**, no exception. |
| **`ARMARAOS_HOME`** | Optional data root. If unset, **`OPENFANG_HOME`**, then **`~/.armaraos`** when that directory exists, else **`~/.openfang`** (same resolution as graph export helpers in **`ainl_graph_memory.py`**). |

## Inbox path

```text
<armaraos_home>/agents/<ARMARAOS_AGENT_ID>/ainl_graph_memory_inbox.json
```

**`is_available()`** requires **`<home>/agents`** to exist as a directory (avoids creating an **`agents/`** tree on machines without ArmaraOS).

## Envelope (on-disk JSON)

Each write produces a full JSON document (not JSONL):

| Field | Meaning |
|-------|---------|
| **`nodes`** | List of **`MemoryNode.to_dict()`** rows (required). |
| **`edges`** | List of edge dicts; preserved across appends (may be empty). |
| **`schema_version`** | String **`"1"`**; defaulted on write. JSON Schema: **`armaraos/bridge/ainl_graph_memory_inbox_schema_v1.json`**. |
| **`source_features`** | String list; every **`push_nodes`** merges **`ainl_graph_memory`** and **`inbox_v1`**. Callers emitting tagger-dependent semantic nodes may add **`requires_ainl_tagger`** (Python constant **`REQUIRES_AINL_TAGGER`** in **`ainl_memory_sync.py`**) per **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md). |

Writes use **`*.tmp`** + **`os.replace`**. In-process concurrency is serialized with **`threading.Lock`** on the writer instance.

## Python API

- **`AinlMemorySyncWriter`**: **`push_nodes`**, **`push_patch`**, **`is_available`**.
- **`SyncResult`**: **`pushed`**, **`skipped`**, **`error`** (`null` on success, **`sync_unavailable`** when disabled, or an I/O message).

**`AINLGraphMemoryBridge._sync`** lazily constructs the writer.

## Tests

**`armaraos/bridge/tests/test_ainl_memory_sync.py`**

## CI

**`.github/workflows/cross-repo-armaraos-bridge.yml`** — builds **armaraos** **`openfang-runtime`** against the public repo so inbox-related Rust stays compatible.

## See also

- **`docs/adapters/AINL_GRAPH_MEMORY.md`** — adapter + runner + read path
- **`docs/ARMARAOS_INTEGRATION.md`** — env table
- **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) — Rust drain, EndTurn order, tagger policy
- **armaraos** [`crates/openfang-runtime/README.md`](https://github.com/sbhooley/armaraos/blob/main/crates/openfang-runtime/README.md) — Cargo features and env toggles
- **armaraos** [`docs/scheduled-ainl.md`](https://github.com/sbhooley/armaraos/blob/main/docs/scheduled-ainl.md) — bundle + cron
