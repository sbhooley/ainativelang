## AINL MySQL Adapter Contract (v1, runtime-native)

Status: **runtime adapter implementation + strict contract wiring**.

This document describes the `mysql` runtime adapter contract for AINL. It follows the same design intent as `sqlite` and `postgres`: explicit verbs, strict SQL classification, table allow-lists, and safe parameter handling.

---

## 1. Purpose

The `mysql` adapter provides direct MySQL access for AINL workflows (tested against MySQL 8.x-compatible deployments).

The adapter is:

- **runtime-native** (registered via `ainl run --enable-adapter mysql`),
- **explicitly gated** by capability allow-lists and security profiles,
- **parameter-safe** (list/tuple/dict params only; never string interpolation),
- **policy-aware** (`allow_write`, table allow-list, privilege tier metadata).

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_MYSQL_URL` (preferred DSN)
- `AINL_MYSQL_HOST`
- `AINL_MYSQL_PORT` (default `3306`)
- `AINL_MYSQL_DB`
- `AINL_MYSQL_USER`
- `AINL_MYSQL_PASSWORD`
- `AINL_MYSQL_SSL_MODE` (default `REQUIRED`)
- `AINL_MYSQL_SSL_CA` (optional CA bundle path)
- `AINL_MYSQL_POOL_MIN` (default `1`)
- `AINL_MYSQL_POOL_MAX` (default `5`)

If `AINL_MYSQL_URL` is not set, `host/db/user` are required.

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter mysql
```

Key flags:

- `--mysql-url`
- `--mysql-host --mysql-port --mysql-db --mysql-user --mysql-password`
- `--mysql-ssl-mode --mysql-ssl-ca`
- `--mysql-timeout-s`
- `--mysql-pool-min --mysql-pool-max`
- `--mysql-allow-write`
- `--mysql-allow-table` (repeatable)

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `mysql` is forbidden.
- `sandbox_network_restricted`: `mysql` can be enabled.

This adapter still respects runtime capability gating and strict contract checks.

---

## 4. Verbs and syntax

### 4.1 `query`

Read-only query execution.

```ainl
L1:
  R mysql.query "SELECT id, email FROM users WHERE id = %s" [42] ->rows
  J rows
```

Returns: `[{...row...}]`

### 4.2 `execute`

Write/DDL execution, only when writes are enabled.

```ainl
L1:
  R mysql.execute "UPDATE users SET active = %s WHERE id = %s" [true, 42] ->out
  J out
```

Returns: `{rows_affected, lastrowid}`

### 4.3 `transaction`

Atomic sequence of `query`/`execute` operations.

```ainl
L1:
  R mysql.transaction [
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
- CTE execution paths are checked for write verbs (`insert|update|delete|replace`) when used with `execute`.
- Table allow-list is enforced by SQL reference scanning (`FROM/JOIN/INTO/UPDATE/TABLE`), including backtick-quoted identifiers.
- Params must be list/tuple/dict; untrusted values must flow through parameters.

---

## 6. Connection behavior

- Uses `pymysql` connections.
- Uses a small built-in queue-based pool for parity with postgres pool ergonomics.
- Falls back to direct per-call connection if pooling is unavailable/empty.
- TLS behavior supports `ssl_mode` plus optional `ssl_ca`.

Implementation references:

- `adapters/mysql/adapter.py`
- `adapters/mysql/sql_guard.py`

---

## 7. Limitations and roadmap

Current limitations:

- No advanced replication/streaming primitives in adapter surface.
- No server-side prepared statement lifecycle API surface.
- Async-capable under the native async runtime loop (`AINL_RUNTIME_ASYNC=1` or `--runtime-async`) with `aiomysql` when installed; sync `pymysql` remains fallback.

Related docs:

- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct DSN path:

```bash
export AINL_MYSQL_URL='mysql://user:pass@localhost:3306/ainl_test'
pytest -m integration tests/test_mysql_adapter_integration.py --mysql-url "$AINL_MYSQL_URL"
```

Turnkey docker path (starts/stops the bundled compose fixture automatically):

```bash
AINL_TEST_USE_DOCKER_MYSQL=1 pytest -m integration tests/test_mysql_adapter_integration.py
# or
make mysql-it
```

Compose fixture file:

- `tests/fixtures/docker-compose.mysql.yml`

When docker mode is enabled, tests auto-set `AINL_MYSQL_URL` for the session (`mysql://ainl:ainl_test_pw_change_me@127.0.0.1:3306/ainl_test`).
