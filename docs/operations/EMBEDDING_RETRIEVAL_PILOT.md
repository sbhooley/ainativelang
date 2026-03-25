# Embedding retrieval pilot (vector search vs `memory.list`)

**Goal:** Replace wide `memory.list` scans with **top-k semantic retrieval** for one workflow at a time.

## Prerequisites

- SQLite memory (`AINL_MEMORY_DB`) with rows in the namespace you index (`AINL_EMBEDDING_INDEX_NAMESPACE`, default `workflow`).
- Sidecar DB: `AINL_EMBEDDING_MEMORY_DB` (default `/tmp/ainl_embedding_memory.sqlite3`).
- `AINL_EMBEDDING_MODE`: start with `stub` for CI/dry runs; use `openai` (or your provider wiring in `adapters/embedding_memory.py`) for real vectors.

## Operator commands

```bash
# Dry-run wrapper (compiles + exercises bridge path)
python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot --dry-run
```

Bridge verbs (from `BridgeTokenBudgetAdapter`): `embedding_workflow_index`, `embedding_workflow_search`.

## Safe rollout

1. **Index** a bounded batch (`embedding_workflow_index` limit defaults apply).  
2. **Query** with a fixed prompt template; inspect `hits` payloads before feeding an LLM.  
3. **Swap** one call site from `memory.list` → search + `memory.get` for returned refs only.  
4. **Measure** prompt token delta before expanding scope.

See [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) and [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md).
