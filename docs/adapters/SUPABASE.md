## AINL Supabase Adapter Contract (v1, runtime-native wrapper)

Status: **runtime wrapper adapter + strict contract wiring**.

This document describes the `supabase` runtime adapter contract for AINL. It follows the same design intent as `dynamodb`/`airtable`/`redis`, but is intentionally a **thin convenience wrapper**:

- DB/table operations delegate to the existing `postgres` adapter.
- Auth/storage use Supabase HTTP endpoints; realtime uses Supabase Realtime WebSocket.

---

## 1. Purpose

The `supabase` adapter provides Supabase-flavored ergonomics for backend workflows while reusing hardened Postgres runtime behavior.

The adapter is:

- **runtime-native wrapper** (`ainl run --enable-adapter supabase`),
- **postgres-delegating** for relational verbs,
- **policy-aware** (`allow_write`, table/bucket/channel allow-lists),
- **network-tier** and explicitly opt-in.

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_SUPABASE_DB_URL` (fallback: `AINL_POSTGRES_URL`)
- `AINL_SUPABASE_URL`
- `AINL_SUPABASE_ANON_KEY`
- `AINL_SUPABASE_SERVICE_ROLE_KEY` (recommended for backend/server workflows)

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter supabase
```

Key flags:

- `--supabase-db-url`
- `--supabase-url`
- `--supabase-anon-key`
- `--supabase-service-role-key`
- `--supabase-timeout-s`
- `--supabase-allow-write`
- `--supabase-allow-table` (repeatable)
- `--supabase-allow-bucket` (repeatable)
- `--supabase-allow-channel` (repeatable)

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `supabase` is forbidden.
- `sandbox_network_restricted`: `supabase` can be enabled.

Use least-privilege PAT/key scopes and prefer service-role usage only in trusted backend contexts.

---

## 4. Verbs and syntax

### 4.1 DB/table wrapper verbs (delegated to postgres)

- `from`, `select`, `query`, `insert`, `update`, `upsert`, `delete`, `rpc`

These return Supabase-style wrappers (`{data, error?}`) while internally using postgres adapter semantics.

### 4.2 Auth verbs

- `auth.sign_up`
- `auth.sign_in_with_password`
- `auth.sign_out`
- `auth.get_user`
- `auth.reset_password_for_email`

Returns: `{ok, data, error?}` envelope.

### 4.3 Storage verbs

- `storage.upload`
- `storage.download`
- `storage.list`
- `storage.remove`
- `storage.get_public_url`

Returns: `{ok, data, error?}` envelope.

### 4.4 Realtime verbs

- `realtime.subscribe`
- `realtime.unsubscribe`
- `realtime.broadcast`
- `realtime.replay`
- `realtime.get_cursor`
- `realtime.ack`

`realtime.subscribe` opens (or reuses) a channel listener task and returns a bounded event batch.
Advanced args include:

- `replay_from` (`"earliest"`, `"latest"`, sequence/timestamp string)
- `fanout_group`
- `consumer`

Events normalize to:

- `{event, schema, table, record, old_record?, sequence?, timestamp?, raw}`

`realtime.replay` returns bounded in-memory historical events for the channel.
`realtime.get_cursor`/`realtime.ack` provide lightweight in-process durable cursor helpers keyed by `channel + fanout_group + consumer`.

---

## 5. Validation and safety rules

- Mutating operations require `allow_write=true`.
- Table allow-list is enforced for DB verbs.
- Bucket allow-list is enforced for storage verbs.
- Channel allow-list is enforced for realtime verbs.
- Table allow-list is enforced for realtime subscribe table filters when provided.
- `realtime.broadcast` requires `allow_write=true`.
- `realtime.ack` requires `allow_write=true`.
- DB SQL/transaction semantics are inherited from `postgres` adapter.

---

## 6. Delegation behavior

- `supabase` DB verbs call into `adapters/postgres/adapter.py` (no duplicated SQL guard logic).
- Non-DB verbs use Supabase HTTP endpoints with bounded retry/backoff for transient failures/rate limits.
- Realtime uses a WebSocket listener task per channel under async runtime mode.

Implementation reference:

- `adapters/supabase/adapter.py`

---

## 7. Limitations and roadmap

Current limitations:

- Realtime fan-out/replay/cursor helpers are intentionally lightweight and process-local (not shared across processes/nodes).
- Replay history is bounded in memory; this is not a durable event log.
- No advanced storage transforms / signed upload workflows.
- No direct Supabase admin schema/migration helper verbs.
- Async-capable under the native async runtime loop (`AINL_RUNTIME_ASYNC=1` or `--runtime-async`) with `httpx.AsyncClient`; DB delegation follows postgres async path when enabled.

Related docs:

- `docs/adapters/POSTGRES.md`
- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct key mode (plus Postgres URL):

```bash
export AINL_TEST_USE_DOCKER_SUPABASE=1
export AINL_POSTGRES_URL='postgresql://user:pass@localhost:5432/ainl_test'
export AINL_SUPABASE_DB_URL="$AINL_POSTGRES_URL"
export AINL_SUPABASE_URL='https://your-project.supabase.co'
export AINL_SUPABASE_SERVICE_ROLE_KEY='ey...'
export AINL_RUNTIME_ASYNC=1
pytest -m integration tests/test_supabase_adapter_integration.py --supabase-url "$AINL_SUPABASE_URL" --supabase-service-role-key "$AINL_SUPABASE_SERVICE_ROLE_KEY"
```

Make helper:

```bash
AINL_TEST_USE_DOCKER_SUPABASE=1 \
AINL_POSTGRES_URL='postgresql://user:pass@localhost:5432/ainl_test' \
AINL_SUPABASE_DB_URL='postgresql://user:pass@localhost:5432/ainl_test' \
AINL_SUPABASE_URL='https://your-project.supabase.co' \
AINL_SUPABASE_SERVICE_ROLE_KEY='ey...' \
make supabase-it
```
