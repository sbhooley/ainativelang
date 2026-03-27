## AINL DynamoDB Adapter Contract (v1, runtime-native)

Status: **runtime adapter implementation + strict contract wiring**.

This document describes the `dynamodb` runtime adapter contract for AINL. It follows the same design intent as `postgres`/`mysql`/`redis`: explicit verbs, strict policy gates, and predictable result shapes.

---

## 1. Purpose

The `dynamodb` adapter provides AWS-native NoSQL access for AINL workflows (single-item CRUD, query/scan, batch, and transactional operations).

The adapter is:

- **runtime-native** (registered via `ainl run --enable-adapter dynamodb`),
- **explicitly gated** by capability allow-lists and security profiles,
- **policy-aware** (`allow_write`, table allow-list),
- **session-reuse aware** (boto3 session/client reuse).

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_DYNAMODB_URL` (optional endpoint override, e.g. local DynamoDB)
- `AINL_DYNAMODB_REGION` (default `us-east-1`)
- Standard AWS credential/env chain:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_SESSION_TOKEN` (optional)
  - `AWS_PROFILE` (optional)

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter dynamodb
```

Key flags:

- `--dynamodb-url`
- `--dynamodb-region`
- `--dynamodb-timeout-s`
- `--dynamodb-allow-write`
- `--dynamodb-allow-table` (repeatable)
- `--dynamodb-consistent-read`

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `dynamodb` is forbidden.
- `sandbox_network_restricted`: `dynamodb` can be enabled.

This adapter still respects runtime capability gating and strict contract checks.

---

## 4. Verbs and syntax

### 4.1 Single-item verbs

- `get`, `put`, `update`, `delete`

### 4.2 Collection verbs

- `query`, `scan`

Returns:

- `{items: [dict, ...], count, last_evaluated_key?}`

### 4.3 Batch/transaction verbs

- `batch_get`, `batch_write`
- `transact_get`, `transact_write`

`transact_get`/`transact_write` return `{ok, results}`.

### 4.4 Health verbs

- `describe_table`, `list_tables`

### 4.5 Streams / realtime (bounded)

- `streams.subscribe`, `streams.unsubscribe`

`streams.subscribe` arguments:

- `table_name`
- `shard_iterator_type` (`LATEST`, `TRIM_HORIZON`, `AT_SEQUENCE_NUMBER`)
- `filter?` (optional object; supports `event_names` and `sequence_number` for `AT_SEQUENCE_NUMBER`)
- `timeout_s?`
- `max_events?`

Returns (normalized, bounded batch):

- `{table, events, active}`
- event shape:
  - `{eventName, eventID?, eventSourceARN?, dynamodb:{Keys, NewImage?, OldImage?, SequenceNumber?}, raw}`

---

## 5. Validation and safety rules

- Mutating verbs require `allow_write=true`:
  - `put`, `update`, `delete`, `batch_write`, `transact_write`
- Optional table allow-list is enforced across table-scoped operations.
- Stream verbs are read-only and follow the same table allow-list enforcement.
- Query/scan pagination shape is normalized (`last_evaluated_key`).
- Expression-attribute values are marshalled through DynamoDB type serializer.
- `streams.subscribe` is bounded by timeout and max events to avoid long-lived blocking in a single graph step.

---

## 6. Connection behavior

- Uses boto3 Session + DynamoDB client.
- Uses boto3 DynamoDB Streams client for stream polling.
- Reuses the initialized client for call lifecycle.
- Supports optional endpoint override for local/testing deployments.
- Native async runtime path (`AINL_RUNTIME_ASYNC=1` / `--runtime-async`) uses background listener tasks + queue batching for non-blocking stream consumption.

Implementation references:

- `adapters/dynamodb/adapter.py`

---

## 7. Limitations and roadmap

Current limitations:

- Stream consumption is intentionally scoped: single-table subscription keying, bounded polling batches, no durable checkpoint replay/KCL fan-out in this pass.
- No PartiQL/DAX in this pass.
- No custom IAM policy generator in adapter surface (use external IAM least-privilege policy management).

Related docs:

- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`
- `docs/reactive/ADVANCED_DURABILITY.md` (Redis/Postgres-backed durable checkpoint patterns for multi-process and multi-node deployments)

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct endpoint/credentials path:

```bash
export AINL_DYNAMODB_URL='http://127.0.0.1:8000'
export AWS_ACCESS_KEY_ID='dummy'
export AWS_SECRET_ACCESS_KEY='dummy'
export AWS_DEFAULT_REGION='us-east-1'
pytest -m integration tests/test_dynamodb_adapter_integration.py --dynamodb-url "$AINL_DYNAMODB_URL"
```

Turnkey docker path (starts/stops the bundled compose fixture automatically):

```bash
AINL_TEST_USE_DOCKER_DYNAMODB=1 pytest -m integration tests/test_dynamodb_adapter_integration.py
# or
make dynamodb-it
```

Compose fixture file:

- `tests/fixtures/docker-compose.dynamodb.yml`
