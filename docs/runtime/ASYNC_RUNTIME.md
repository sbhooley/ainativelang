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

## Observability (optional)

Reactive observability hooks are available but disabled by default.

- Env: `AINL_OBSERVABILITY=1`
- CLI: `ainl run ... --observability`
- Optional JSONL sink: `AINL_OBSERVABILITY_JSONL=/path/to/metrics.jsonl` or `--observability-jsonl /path/to/metrics.jsonl`

When enabled, the runtime emits lightweight structured metric events (JSON lines, stderr) around adapter calls:

- `adapter.call.duration_ms` (latency per adapter verb call)
- `reactive.events_per_batch` (subscribe/replay batch size)
- `reactive.lag_seconds` (where timestamped events are available, e.g. Supabase Realtime)
- `reactive.sequence_gap` (best-effort sequence gap estimate)
- `reactive.ack.total`, `reactive.ack.success`, `reactive.ack.success_rate`

This path is intentionally lightweight and no-op when disabled.

Example with file sink:

```bash
AINL_RUNTIME_ASYNC=1 AINL_OBSERVABILITY=1 AINL_OBSERVABILITY_JSONL=/tmp/ainl-metrics.jsonl \
  ainl run examples/reactive/observability_reactive_smoke.ainl \
  --runtime-async --observability --observability-jsonl /tmp/ainl-metrics.jsonl \
  --enable-adapter redis --redis-allow-prefix events: --redis-allow-write
```

The JSONL sink is append-only and compatible with tools like `jq`, `vector`, `promtail`, or simple log shipping pipelines.

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
