# Embedding retrieval pilot (vector search vs `memory.list`)

**Goal:** Replace wide `memory.list` scans with **top-k semantic retrieval** for one workflow at a time.

## Prerequisites

- SQLite memory (`AINL_MEMORY_DB`) with rows in the namespace you index (`AINL_EMBEDDING_INDEX_NAMESPACE`, default `workflow`).
- Sidecar DB: `AINL_EMBEDDING_MEMORY_DB` (default `/tmp/ainl_embedding_memory.sqlite3`).
- `AINL_EMBEDDING_MODE`: start with `stub` for CI/dry runs; use `openai` (or your provider wiring in `adapters/embedding_memory.py`) for real vectors.

## What gets indexed (so vector search actually returns text)

`embedding_workflow_index` embeds the SQLite memory record `payload` (not just metadata).

For session bootstrap vector retrieval, this repo’s proactive session summarizer writes the actual bullet summary text into `payload.summary` for `workflow.session_summary` records, so `embedding_workflow_search` can return `payload_snapshot.summary` for use in token-aware startup.

## Operator commands

```bash
# Dry-run wrapper (compiles + exercises bridge path)
python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot --dry-run
```

Bridge verbs (from `BridgeTokenBudgetAdapter`): `embedding_workflow_index`, `embedding_workflow_search`.

## Enable vector search for session bootstrap (optional; safe fallback)

1. Set real embedding mode:
   - `AINL_EMBEDDING_MODE=openai`
2. Run the pilot indexer at least once (so the embedding sidecar has refs):
   - `python3 openclaw/bridge/run_wrapper_ainl.py embedding-memory-pilot`
3. Ensure the profile enables the startup embedding path:
   - `AINL_STARTUP_USE_EMBEDDINGS=1` (already set in `openclaw-default` / `cost-tight` profiles)

When real vectors are enabled, `token_aware_startup_context.lang` will try embedding top-k first; if hits are empty, it falls back to reading `MEMORY.md` (so it shouldn’t break chat sessions).

## Safe rollout

1. **Index** a bounded batch (`embedding_workflow_index` limit defaults apply).  
2. **Query** with a fixed prompt template; inspect `hits` payloads before feeding an LLM.  
3. **Swap** one call site from `memory.list` → search + `memory.get` for returned refs only.  
4. **Measure** prompt token delta before expanding scope.

See [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) and [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md).
