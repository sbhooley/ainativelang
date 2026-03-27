## AINL Postgres Adapter Contract (v1, runtime-native)

Status: **runtime adapter implementation + strict contract wiring**.

This document describes the `postgres` runtime adapter contract for AINL. It follows the same design intent as `sqlite`: explicit verbs, strict SQL classification, table allow-lists, and safe parameter handling.

---

## 1. Purpose

The `postgres` adapter provides direct PostgreSQL access for AINL workflows, including hosted Postgres-compatible deployments (Supabase, AWS RDS for PostgreSQL, Neon, and self-managed Postgres).

The adapter is:

- **runtime-native** (registered via `ainl run --enable-adapter postgres`),
- **explicitly gated** by capability allow-lists and security profiles,
- **parameter-safe** (list/tuple/dict params only; never string interpolation),
- **policy-aware** (`allow_write`, table allow-list, privilege tier metadata).

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_POSTGRES_URL` (preferred DSN)
- `AINL_POSTGRES_HOST`
- `AINL_POSTGRES_PORT` (default `5432`)
- `AINL_POSTGRES_DB`
- `AINL_POSTGRES_USER`
- `AINL_POSTGRES_PASSWORD`
- `AINL_POSTGRES_SSLMODE` (default `require`)
- `AINL_POSTGRES_SSLROOTCERT` (optional CA bundle path)
- `AINL_POSTGRES_POOL_MIN` (default `1`)
- `AINL_POSTGRES_POOL_MAX` (default `5`)

If `AINL_POSTGRES_URL` is not set, `host/db/user` are required.

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter postgres
```

Key flags:

- `--postgres-url`
- `--postgres-host --postgres-port --postgres-db --postgres-user --postgres-password`
- `--postgres-sslmode --postgres-sslrootcert`
- `--postgres-timeout-s --postgres-statement-timeout-ms`
- `--postgres-pool-min --postgres-pool-max`
- `--postgres-allow-write`
- `--postgres-allow-table` (repeatable)

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `postgres` is forbidden.
- `sandbox_network_restricted`: `postgres` can be enabled.

This adapter still respects runtime capability gating and strict contract checks.

---

## 4. Verbs and syntax

### 4.1 `query`

Read-only query execution.

```ainl
L1:
  R postgres.query "SELECT id, email FROM users WHERE id = %s" [42] ->rows
  J rows
```

Returns: `[{...row...}]`

### 4.2 `execute`

Write/DDL execution, only when writes are enabled.

```ainl
L1:
  R postgres.execute "UPDATE users SET active = %s WHERE id = %s" [true, 42] ->out
  J out
```

Returns: `{rows_affected, lastrowid}`

### 4.3 `transaction`

Atomic sequence of `query`/`execute` operations.

```ainl
L1:
  R postgres.transaction [
    {"verb":"execute","sql":"INSERT INTO users(email) VALUES (%s)","params":["a@x.dev"]},
    {"verb":"query","sql":"SELECT COUNT(*) AS c FROM users","params":[]}
  ] ->txn
  J txn
```

Returns: `{ok, results}`

If any operation fails, transaction is rolled back and an adapter error is raised.

---

## 5. Validation and safety rules

- `query` must be `SELECT`/`WITH`/`EXPLAIN SELECT` shaped SQL.
- `execute` must be write/DDL shaped SQL and requires `allow_write=true`.
- CTE execution paths are checked for write verbs (`insert|update|delete|merge`) when used with `execute`.
- Table allow-list is enforced by SQL reference scanning (`FROM/JOIN/INTO/UPDATE/TABLE`).
- Params must be list/tuple/dict; untrusted values must flow through parameters.

---

## 6. Connection behavior

- Uses `psycopg` connections with per-session `statement_timeout`.
- Uses `psycopg_pool.ConnectionPool` when available.
- Falls back to direct per-call connection if pool module is unavailable.
- TLS behavior supports `sslmode` and optional `sslrootcert`.

Implementation references:

- `adapters/postgres/adapter.py`
- `adapters/postgres/sql_guard.py`

---

## 7. Limitations and roadmap

Current limitations:

- No LISTEN/NOTIFY support.
- No server-side prepared statement management API surface.
- Async-capable under the native async runtime loop (`AINL_RUNTIME_ASYNC=1` or `--runtime-async`) with `psycopg.AsyncConnection`; sync remains default fallback.

Related docs:

- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct DSN path:

```bash
export AINL_POSTGRES_URL='postgresql://user:pass@localhost:5432/ainl_test'
pytest -m integration tests/test_postgres_adapter_integration.py --postgres-url "$AINL_POSTGRES_URL"
```

Turnkey docker path (starts/stops the bundled compose fixture automatically):

```bash
AINL_TEST_USE_DOCKER_POSTGRES=1 pytest -m integration tests/test_postgres_adapter_integration.py
# or
make postgres-it
```

Compose fixture file:

- `tests/fixtures/docker-compose.postgres.yml`

When docker mode is enabled, tests auto-set `AINL_POSTGRES_URL` for the session (`postgresql://ainl:ainl_test_pw_change_me@127.0.0.1:5432/ainl_test`).
