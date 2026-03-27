## AINL Redis Adapter Contract (v1, runtime-native)

Status: **runtime adapter implementation + strict contract wiring**.

This document describes the `redis` runtime adapter contract for AINL. It follows the same design intent as `postgres`/`mysql`: explicit verbs, strict policy gates, and predictable result shapes.

---

## 1. Purpose

The `redis` adapter provides Redis-backed cache/session/queue/pubsub primitives for AINL workflows.

The adapter is:

- **runtime-native** (registered via `ainl run --enable-adapter redis`),
- **explicitly gated** by capability allow-lists and security profiles,
- **policy-aware** (`allow_write`, key/channel prefix policy),
- **pool-aware** (uses redis-py connection pooling via client/pool internals).

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_REDIS_URL` (preferred DSN, e.g. `redis://user:pass@host:6379/0`)
- `AINL_REDIS_HOST`
- `AINL_REDIS_PORT` (default `6379`)
- `AINL_REDIS_DB` (default `0`)
- `AINL_REDIS_USER`
- `AINL_REDIS_PASSWORD`
- `AINL_REDIS_SSL` (boolean-like env)

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter redis
```

Key flags:

- `--redis-url`
- `--redis-host --redis-port --redis-db --redis-user --redis-password`
- `--redis-ssl`
- `--redis-timeout-s`
- `--redis-allow-write`
- `--redis-allow-prefix` (repeatable; scopes keys/channels)

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `redis` is forbidden.
- `sandbox_network_restricted`: `redis` can be enabled.

This adapter still respects runtime capability gating and strict contract checks.

---

## 4. Verbs and syntax

### 4.1 Key/value

- `get`, `set`, `delete`, `incr`, `decr`

```ainl
L1:
  R redis.set "session:42" "{\"status\":\"active\"}" 300 ->s
  R redis.get "session:42" ->v
  J v
```

### 4.2 Hashes

- `hget`, `hset`, `hdel`, `hmget`

### 4.3 Lists / simple queues

- `lpush`, `rpush`, `lpop`, `rpop`, `llen`

### 4.4 Pub/sub

- `publish`, `subscribe`

`subscribe` returns `{channel, messages}` and is bounded by timeout/message-count args.

### 4.5 Health

- `ping`, `info`

### 4.6 Transaction

Atomic sequence via pipeline:

```ainl
L1:
  R redis.transaction [
    {"verb":"set","args":["workflow:step","done"]},
    {"verb":"get","args":["workflow:step"]}
  ] ->txn
  J txn
```

Returns: `{ok, results}`

---

## 5. Validation and safety rules

- Write verbs require `allow_write=true`.
- Optional prefix policy (`allow_prefixes`) is enforced for keys/channels.
- `transaction` accepts a non-empty list of `{verb, args}` operations.
- `subscribe` is bounded by timeout and max_messages to avoid unbounded blocking.

---

## 6. Connection behavior

- Uses `redis-py` client with URL-first config.
- Uses Redis client's built-in connection pool behavior.
- Async-capable under the native async runtime loop (`AINL_RUNTIME_ASYNC=1` or `--runtime-async`) using `redis.asyncio` with full verb parity (`KV`, `hash`, `list`, `pub/sub`, `transaction`, `health`) when available; sync remains fallback.

Implementation references:

- `adapters/redis/adapter.py`

---

## 7. Limitations and roadmap

Current limitations:

- No RedisJSON/Graph/Streams module-specific primitives in this pass.
- No Sentinel/Cluster explicit configuration surface yet (URL/manual topology only).
- Pub/sub listening remains bounded by timeout + max_messages to avoid long-lived blocking in a single graph step.

Related docs:

- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct DSN path:

```bash
export AINL_REDIS_URL='redis://localhost:6379/0'
pytest -m integration tests/test_redis_adapter_integration.py --redis-url "$AINL_REDIS_URL"
```

Turnkey docker path (starts/stops the bundled compose fixture automatically):

```bash
AINL_TEST_USE_DOCKER_REDIS=1 pytest -m integration tests/test_redis_adapter_integration.py
# or
make redis-it
```

Compose fixture file:

- `tests/fixtures/docker-compose.redis.yml`
