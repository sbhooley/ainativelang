# Graph memory inbox sync (Python → ArmaraOS)

Scheduled `ainl run` jobs and the ArmaraOS Python bridge mutate graph memory through `GraphStore` (JSON overlay) while Rust holds the canonical per-agent store in `ainl_memory.db`. Python can push **append-only** snapshots of new nodes into a small JSON **inbox** file that the daemon may ingest (non-blocking, best-effort).

## Environment variables

| Variable | Meaning |
|----------|---------|
| `ARMARAOS_AGENT_ID` | Required for sync. When unset, all inbox operations no-op with `SyncResult(error="sync_unavailable")`. |
| `ARMARAOS_HOME` | Optional. ArmaraOS / OpenFang data root (same precedence as graph export: falls back to `OPENFANG_HOME`, then `~/.armaraos` if that directory exists, else `~/.openfang`). |

## Inbox file path

```
${ARMARAOS_HOME or ~/.armaraos or ~/.openfang}/agents/<ARMARAOS_AGENT_ID>/ainl_graph_memory_inbox.json
```

Sync is enabled only when `ARMARAOS_AGENT_ID` is set **and** the directory `<home>/agents` already exists (so standalone `ainl run` without an ArmaraOS install does not create stray trees).

## File format

The inbox uses the same top-level JSON shape as `GraphStore` exports:

```json
{
  "nodes": [ { "...": "MemoryNode.to_dict() row" } ],
  "edges": []
}
```

Each successful `push_nodes` / `push_patch` read–merge–writes the file **atomically** (write to `*.tmp` then `os.replace`), matching `GraphStore._atomic_save_unlocked`. Concurrent writers in a single process are serialized with a lock; multi-process races may still lose an interleaved append (same limitation as export refresh).

## Python API

- `armaraos.bridge.ainl_memory_sync.AinlMemorySyncWriter`
- `AINLGraphMemoryBridge` exposes `_sync` (lazy) for hooks and the bridge runner.

Rust ingest of `ainl_graph_memory_inbox.json` is **not** implemented in this repository; the contract is documented here for kernel/worker alignment.
