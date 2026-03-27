## Reactive Events in AINL

AINL treats **reactive workflows** (change feeds, pub/sub, webhooks) as **first-class but bounded** event sources that feed into the same deterministic graph runtime as synchronous calls.

This document is a high-level map of:

- **Event sources** and their **normalized shapes**
- **Patterns** for building durable, idempotent pipelines
- How to **integrate with the native async runtime**
- When to choose each source

---

### 1. Event Sources and Shapes

AINL exposes reactive inputs primarily through **adapters**:

- **DynamoDB Streams** (`dynamodb` adapter)
  - Verbs: `streams.subscribe`, `streams.unsubscribe`, `streams.get_checkpoint`, `streams.ack`
  - Shape (per event, normalized):
    - `eventName`: `"INSERT" | "MODIFY" | "REMOVE" | "UNKNOWN"`
    - `eventID`
    - `eventSourceARN`
    - `dynamodb.Keys` (deserialized dict)
    - `dynamodb.NewImage?` / `dynamodb.OldImage?` (deserialized dicts)
    - `dynamodb.SequenceNumber?`
    - `raw` (original record)

- **Supabase Realtime** (`supabase` adapter)
  - Verbs: `realtime.subscribe`, `realtime.unsubscribe`, `realtime.broadcast`, `realtime.replay`, `realtime.get_cursor`, `realtime.ack`
  - Shape (per event, normalized):
    - `event`: `"INSERT" | "UPDATE" | "DELETE" | "BROADCAST" | "SYSTEM"`
    - `schema`: e.g. `"public"`
    - `table`
    - `record?` / `old_record?`
    - `sequence?` (commit timestamp / sequence token)
    - `timestamp?`
    - `raw`

- **Redis Pub/Sub** (`redis` adapter)
  - Verbs: `publish`, `subscribe`
  - Shape (per message, normalized):
    - adapter returns `{channel, messages: [value, ...], active}` where `value` is the decoded payload

- **Airtable Webhooks** (`airtable` adapter)
  - Verbs: `webhook.create`, `webhook.list`, `webhook.delete` (registration), plus regular HTTP entrypoints in the host
  - Shape: webhook payloads are delivered to your HTTP host; AINL graphs typically ingest them through `http` or `bridge` adapters and normalize into per-record events before further processing.

Each adapter returns **bounded batches**:

- `streams.subscribe` → `{table, events: [...], active, consumer_group?, consumer_id?}`
- `supabase.realtime.subscribe` → `{ok, result: {channel, events: [...], active, fanout_group?, consumer?}}`
- `redis.subscribe` → `{channel, messages: [...], active}`

---

### 2. Choosing the Right Source

Use this table as a rough decision guide:

| Source | Primary strength | When to prefer it |
|--------|------------------|-------------------|
| **DynamoDB Streams** | Ordered change capture on DynamoDB tables with per-shard sequence numbers | High-volume backend tables on AWS where you already use DynamoDB, need ordered change feeds, and want checkpointable consumers |
| **Supabase Realtime** | Postgres row changes + broadcast in a managed Supabase project | SaaS/web apps on Supabase where you want live UI updates, workspace events, or light fan-out/replay semantics on top of Postgres |
| **Redis Pub/Sub** | Lightweight ephemeral messaging and fan-out inside your infra | Low-latency, ephemeral channels (notifications, fan-out, coordination) where durability lives elsewhere (DB, memory) |
| **Airtable Webhooks** | No‑code friendly entrypoint from Airtable tables | Prototypes, operations, or non-engineering teams that live in Airtable and want graph-native processing downstream |

If more than one source fits, anchor on **where your authoritative state lives today** and **how much durability / ordering you need**:

- Prefer **DynamoDB Streams** for strongly-ordered table change capture.
- Prefer **Supabase Realtime** for app-centric, multi-tenant Postgres + broadcast.
- Prefer **Redis** for short-lived, infra-local signaling and fan-out.
- Prefer **Airtable webhooks** when Airtable is the source of truth and teams already operate there.

---

### 3. Patterns

Reactive graphs in AINL typically follow one of these shapes:

1. **Change → Embeddings pipeline**
   - Source: `dynamodb.streams.subscribe` or `supabase.realtime.subscribe`
   - Steps:
     - Poll bounded events (async)
     - For each event, extract the record payload
     - Call an embedding adapter / workflow
     - Persist embedding or derived state to `memory` / DB
     - Acknowledge checkpoint (`streams.ack` / `realtime.ack`)

2. **Multi-consumer fan-out**
   - Source: Supabase Realtime (fanout groups, cursors) or Redis Pub/Sub
   - Steps:
     - Each consumer uses a distinct `fanout_group` / `consumer_id` (Supabase) or channel pattern (Redis)
     - Process a bounded batch of events
     - Record the last processed cursor or sequence in `memory`
     - Use that state to decide what to replay or skip on the next run

3. **Idempotent processing with checkpoints**
   - Source: DynamoDB Streams or Supabase Realtime
   - Steps:
     - Retrieve last checkpoint (`streams.get_checkpoint` / `realtime.get_cursor`) from adapter or `memory`
     - Subscribe with `checkpoint_mode="memory"` (DynamoDB) or `replay_from` (Supabase)
     - Process new events only
     - Write an **idempotency key** (e.g., SequenceNumber or `sequence`) to `memory`
     - Ack the new checkpoint

4. **Hybrid pipelines**
   - Sources: combine DB streams + broadcast + pub/sub
   - Example flow:
     - DDB Streams → process raw change
     - Supabase Realtime → broadcast a normalized event to web clients
     - Redis Pub/Sub → publish a simplified notification to infra-local consumers
     - Memory/DB → record last processed sequence for idempotency

Concrete example graphs for these patterns live in `examples/reactive/`.

---

### 4. Async Runtime Integration

Reactive adapters are designed to work **with** the native async runtime:

- Enable async: `AINL_RUNTIME_ASYNC=1` or `ainl run --runtime-async ...`
- Use bounded calls:
  - `R dynamodb.streams.subscribe ... ->out`
  - `R supabase.realtime.subscribe ... ->out`
  - `R redis.subscribe ... ->out`
- Each call:
  - runs **non-blocking** in the async loop,
  - returns a bounded batch (`timeout_s`, `max_events`),
  - and can be wrapped in retries / loops like any other `R` step.

Long-lived listeners are implemented as **background tasks** behind these verbs. Graphs see a simple, repeatable pattern: *call → get bounded events → update state → ack/checkpoint → repeat later*.

---

### 5. Limitations and Best Practices

- **Process-local helpers:** DynamoDB Streams checkpoints and Supabase Realtime cursors are stored **in-process** in this release. They are suitable for single-runner setups or as building blocks for external durability (e.g., `memory` or Redis-backed checkpoints), but they are **not** a full KCL or multi-node coordination system.
- **Bounded polling:** Always set sensible `timeout_s` and `max_events` to avoid unbounded loops; reactive verbs are designed for **polling**, not infinite blocking.
- **Idempotency:** Treat SequenceNumber / `sequence` / `timestamp` as idempotency keys and record them in `memory` or a DB when possible. This makes replay and recovery much simpler.
- **Security:** Streams and realtime adapters obey the same `allow_tables` / `allow_channels` / `allow_write` gates and privilege tiers as their non-reactive verbs. Keep them in appropriate security profiles.
- **Host responsibilities:** Durable queueing, multi-node balancing, and hard multi-tenant boundaries remain the responsibility of the host (Kubernetes, queueing systems, or external stream processors).

For deeper adapter-specific details, see:

- `docs/adapters/DYNAMODB.md` (Streams section)
- `docs/adapters/SUPABASE.md` (Realtime section)
- `docs/adapters/REDIS.md` (Pub/Sub + async)
- `docs/adapters/AIRTABLE.md` (Webhooks + attachments)

