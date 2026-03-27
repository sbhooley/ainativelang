# Advanced Durability Patterns for Reactive Graphs

No new adapter code required - use existing `redis` and `postgres` adapters in your graphs.

## 1. Overview

AINL's current default checkpoint/cursor helpers are process-local by design. This is enough for many single-runner deployments because it keeps reactive flows simple and fast.

For multi-process or multi-node deployments, process-local state is not sufficient on its own:

- a restart can lose in-memory cursor/checkpoint state
- multiple workers need shared coordination state
- cross-node failover needs a durable handoff point

Goal: use existing adapters to persist checkpoints/cursors durably, without runtime or adapter changes.

---

## 2. Pattern 1: Redis-backed Checkpoints (Recommended for speed)

Use Redis as a fast shared store for last-acked position.

### How it works

1. Before subscribe, load the latest position from Redis with `redis.get`.
2. Feed it into the reactive source (`replay_from` for Supabase, or sequence/filter for DynamoDB subscribe mode).
3. After successful processing + `streams.ack` / `realtime.ack`, write the new position via `redis.set`.

Use a composite key that is stable and unique per stream consumer:

`checkpoint:dynamodb:<table>:<group>:<consumer>:<shard>`

or

`checkpoint:supabase:<channel>:<group>:<consumer>`

### Reusable snippet (load from Redis -> subscribe -> ack -> redis.set)

```ainl
# Load durable checkpoint from Redis (shared across workers)
L_LOAD:
  R redis.get "checkpoint:dynamodb:orders:workers:consumer-a:shard-000" ->last_seq
  J last_seq

# Subscribe using last known sequence (adapter-local checkpoint helpers remain memory mode)
L_SUBSCRIBE:
  R dynamodb.streams.subscribe "orders" {
    "shard_iterator_type": "AT_SEQUENCE_NUMBER",
    "filter": {"sequence_number": last_seq, "event_names": ["INSERT","MODIFY","REMOVE"]},
    "checkpoint_mode": "memory",
    "consumer_group": "workers",
    "consumer_id": "consumer-a",
    "timeout_s": 2,
    "max_events": 50
  } ->batch
  J batch

# After processing events and acking, persist latest sequence to Redis
L_ACK_AND_SAVE:
  R dynamodb.streams.ack "orders" {
    "consumer_group": "workers",
    "consumer_id": "consumer-a",
    "shard_id": "shard-000",
    "sequence": latest_seq
  } ->ack_out
  R redis.set "checkpoint:dynamodb:orders:workers:consumer-a:shard-000" latest_seq 86400 ->saved
  J {"ack": ack_out, "saved": saved}
```

Notes:

- Keep TTL long enough for restart windows (or omit TTL for strict durability).
- Only write Redis after business side effects + ack logic succeed.
- Use idempotency keys (`SequenceNumber` / `sequence`) to safely replay.

---

## 3. Pattern 2: Postgres-backed Durable Cursors (Recommended for strong consistency)

Use Postgres as the source of truth for checkpoints/cursors. This is slower than Redis but offers stronger operational consistency and auditability.

### One-time table (startup/bootstrap)

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
  adapter   TEXT NOT NULL,
  stream    TEXT NOT NULL,
  grp       TEXT NOT NULL,
  consumer  TEXT NOT NULL,
  shard     TEXT NOT NULL,
  sequence  TEXT NOT NULL,
  ts        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (adapter, stream, grp, consumer, shard)
);
```

### How it works

1. At startup, `postgres.query` the latest sequence/cursor row.
2. Subscribe/replay from that sequence.
3. After successful ack, `postgres.execute` an UPSERT for `(adapter, stream, grp, consumer, shard, sequence, ts)`.

### Reusable snippet (startup read -> subscribe -> ack -> UPSERT)

```ainl
# Bootstrap durable cursor from Postgres
L_LOAD_CURSOR:
  R postgres.query "SELECT sequence FROM checkpoints WHERE adapter = %s AND stream = %s AND grp = %s AND consumer = %s AND shard = %s" ["dynamodb","orders","workers","consumer-a","shard-000"] ->rows
  J rows

# Subscribe/replay from the loaded sequence
L_SUBSCRIBE:
  R dynamodb.streams.subscribe "orders" {
    "shard_iterator_type": "AT_SEQUENCE_NUMBER",
    "filter": {"sequence_number": rows[0].sequence},
    "checkpoint_mode": "memory",
    "consumer_group": "workers",
    "consumer_id": "consumer-a",
    "timeout_s": 2,
    "max_events": 50
  } ->batch
  J batch

# Ack then UPSERT durable checkpoint
L_ACK_AND_UPSERT:
  R dynamodb.streams.ack "orders" {
    "consumer_group": "workers",
    "consumer_id": "consumer-a",
    "shard_id": "shard-000",
    "sequence": latest_seq
  } ->ack_out
  R postgres.execute "INSERT INTO checkpoints (adapter, stream, grp, consumer, shard, sequence, ts) VALUES (%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT (adapter, stream, grp, consumer, shard) DO UPDATE SET sequence = EXCLUDED.sequence, ts = EXCLUDED.ts" ["dynamodb","orders","workers","consumer-a","shard-000",latest_seq] ->upsert_out
  J {"ack": ack_out, "upsert": upsert_out}
```

Notes:

- Prefer transactional coupling when you also write business data in Postgres.
- Keep the checkpoint row write as the final step after processing success.
- For Supabase realtime, map `stream`/`shard` to `channel` and a logical partition key.

---

## 4. Pattern 3: Hybrid (Redis hot path + Postgres durability)

Use Redis for low-latency reads/writes on every batch, and periodically mirror or dual-write checkpoints to Postgres for durable recovery and audits.

Use this when:

- hot-path latency matters, and
- you need stronger recovery guarantees than Redis-only.

A practical setup:

- every ack -> `redis.set`
- every N acks or every T seconds -> Postgres UPSERT
- on restart -> try Redis first, fall back to Postgres if missing

---

## 5. Best Practices and Trade-offs

- **Idempotency first:** treat sequence/cursor as idempotency key; make downstream writes replay-safe.
- **Partial failures:** only advance durable checkpoint after your side effects are committed.
- **Retries:** retry transient adapter failures with bounded retries and backoff; never blindly skip failed batches.
- **State choice:**
  - in-memory only: single-runner, lowest complexity
  - Redis: shared fast checkpointing for distributed workers
  - Postgres: strongest consistency and auditability
  - Hybrid: speed + durable fallback
- **Observability tie-in:** monitor `reactive.ack.success_rate`, `reactive.sequence_gap`, `reactive.events_per_batch`, and `adapter.call.duration_ms` to detect lag, drops, and write-path regressions early.

---

## 6. Packaged Templates

AINL now ships optional packaged helpers in `templates/durability/`:

- `templates/durability/redis_checkpoint_helpers.ainl`
- `templates/durability/postgres_checkpoint_helpers.ainl`

Both templates are documentation-level helpers you can include or copy/paste. They require no runtime/adapter changes.

### How to use

Option A (recommended): include a template and call helper labels.

```ainl
include "templates/durability/redis_checkpoint_helpers.ainl" as dredis

S app core my_reactive_worker
LENTRY:
  # Load shared checkpoint (Redis)
  Call dredis/LOAD_CHECKPOINT ->cp

  # Your app-specific subscribe/process flow...
  # (replace with your own table/channel and processing logic)
  R dynamodb.streams.subscribe "orders" "LATEST" null 1 25 "workers" "consumer-a" "memory" ->sub
  If sub.events == [] ->LNO_EVENTS ->LHAS_EVENTS

LNO_EVENTS:
  J {"processed": 0}

LHAS_EVENTS:
  R core.GET sub.events 0 ->evt
  R core.GET evt.dynamodb "SequenceNumber" ->latest_seq
  # Persist checkpoint with existing redis adapter
  R redis.set "checkpoint:dynamodb:orders:workers:consumer-a:shard-000" latest_seq 86400 ->saved
  J {"processed": 1, "checkpoint_saved": saved}
```

Option B: copy the template labels into your graph and replace placeholder constants.

Tips:

- Keep composite key naming consistent across services.
- Replace `"REPLACE_WITH_LATEST_SEQUENCE"` placeholders with your event-derived sequence/cursor.
- Use the Redis template for fastest shared checkpointing; use Postgres template for stronger consistency/auditability.

## 7. Cross-references

- Core reactive guide: `docs/reactive/REACTIVE_EVENTS.md`
- DynamoDB streams contract: `docs/adapters/DYNAMODB.md`
- Supabase realtime contract: `docs/adapters/SUPABASE.md`
- Redis adapter contract: `docs/adapters/REDIS.md`
- Postgres adapter contract: `docs/adapters/POSTGRES.md`

This guide is intentionally documentation-only: no runtime or adapter changes are required.

---

## 8. Production Starter Templates

For teams that want a "start here and customize" production baseline, use:

- `templates/production/dynamodb_stream_worker.ainl`
- `templates/production/supabase_realtime_worker.ainl`
- `templates/production/hybrid_stream_to_realtime.ainl`

These templates bundle durability flow + observability-friendly outputs and are designed for:

- `--runtime-async`
- `--observability`
- `--observability-jsonl`

No new adapter/runtime code is required. They use existing adapters only (`redis`, `postgres`, `dynamodb`, `supabase`).

### Quick usage

```bash
AINL_RUNTIME_ASYNC=1 AINL_OBSERVABILITY=1 AINL_OBSERVABILITY_JSONL=/tmp/ainl-reactive-metrics.jsonl \
  ainl run templates/production/hybrid_stream_to_realtime.ainl \
  --runtime-async --observability --observability-jsonl /tmp/ainl-reactive-metrics.jsonl \
  --enable-adapter dynamodb --enable-adapter supabase --enable-adapter redis
```

Treat each template as a production starter:

1. replace stream/channel/table constants
2. insert your business logic in the Process section
3. keep Ack + Persist and observability fields intact
