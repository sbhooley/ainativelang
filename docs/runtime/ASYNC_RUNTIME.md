# Async Runtime

AINL runtime execution remains backward-compatible and sync-first by default.
This document describes the optional native async runtime path.

## Enable async mode

- Env: `AINL_RUNTIME_ASYNC=1`
- CLI: `ainl run ... --runtime-async`

If neither is set, runtime behaves exactly as before.

## Native async behavior

- Runtime now has a native async label loop (`run_label_async`) and async graph/step execution path.
- `R` operations await adapter `call_async(...)` directly in the async engine.
- Sync mode (`run_label`) remains unchanged and default.
- If an adapter does not implement async behavior, async path gracefully falls back to sync adapter calls where needed.
- Multiple async label executions can run concurrently via `asyncio.gather(...)` for I/O-heavy workloads.

## Adapter coverage (current pass)

- `postgres`: async-capable (`psycopg.AsyncConnection` + optional async pool)
- `mysql`: async-capable (`aiomysql` when installed; sync fallback otherwise)
- `redis`: async-capable (`redis.asyncio`) with full verb parity for KV/hash/list/pubsub/transaction/health
- `supabase`: async-capable (`httpx.AsyncClient` + async-aware postgres delegation)
- `dynamodb`: async-capable for streams subscribe/unsubscribe batching (CRUD/query/scan/batch/transact remain sync-compatible via safe fallback)
- `airtable`: async-capable for attachment/webhook extension verbs (core CRUD/list flows remain sync-compatible via safe fallback)
- `sqlite`: sync-only, unchanged

## Safety and policy

Security profiles, effect analysis, adapter allowlists, and capability gates are unchanged in async mode.
Async mode affects execution transport only, not policy semantics.

## Current limitations

- Redis pub/sub remains intentionally bounded per call (timeout + max_messages), which is safer for workflow execution but not a permanent stream consumer model by default.
- DynamoDB streams support is scoped to bounded polling batches and simple subscription lifecycle; advanced shard fan-out/checkpoint durability is future work.
- Supabase realtime includes websocket subscribe/unsubscribe/broadcast plus lightweight in-process fan-out/replay/cursor helpers; multi-node durable replay remains future work.
- Some adapters remain sync-only (`sqlite`).

## Testing

Core async dispatch test:

```bash
pytest tests/test_async_dispatch.py
```

Integration (optional env-gated async path checks):

```bash
AINL_RUNTIME_ASYNC=1 pytest -m integration tests/test_postgres_adapter_integration.py
AINL_RUNTIME_ASYNC=1 pytest -m integration tests/test_mysql_adapter_integration.py
AINL_RUNTIME_ASYNC=1 pytest -m integration tests/test_redis_adapter_integration.py
AINL_RUNTIME_ASYNC=1 pytest -m integration tests/test_airtable_adapter_integration.py
AINL_RUNTIME_ASYNC=1 pytest -m integration tests/test_supabase_adapter_integration.py
```
