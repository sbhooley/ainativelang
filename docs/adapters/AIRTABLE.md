## AINL Airtable Adapter Contract (v1, runtime-native)

Status: **runtime adapter implementation + strict contract wiring**.

This document describes the `airtable` runtime adapter contract for AINL. It follows the same design intent as `redis`/`dynamodb`: explicit verbs, strict policy gates, and predictable result shapes.

---

## 1. Purpose

The `airtable` adapter provides no-code-friendly table and record operations for startup/prototype workflows.

The adapter is:

- **runtime-native** (registered via `ainl run --enable-adapter airtable`),
- **explicitly gated** by capability allow-lists and security profiles,
- **policy-aware** (`allow_write`, table allow-list),
- **db-contract aligned** where natural (`list/find/create/update/delete` map to read/create/update/delete flow).

---

## 2. Configuration

### 2.1 Environment variables

- `AINL_AIRTABLE_API_KEY` (required PAT)
- `AINL_AIRTABLE_BASE_ID` (required)

### 2.2 CLI flags

Enable adapter:

```bash
ainl run your.ainl --enable-adapter airtable
```

Key flags:

- `--airtable-api-key`
- `--airtable-base-id`
- `--airtable-timeout-s`
- `--airtable-max-page-size`
- `--airtable-allow-write`
- `--airtable-allow-table` (repeatable)
- `--airtable-allow-attachment-host` (repeatable, optional)

---

## 3. Security and privilege model

Adapter metadata in `tooling/adapter_manifest.json`:

- `privilege_tier`: `network`
- `destructive`: `true`
- `network_facing`: `true`
- `sandbox_safe`: `false`

Security profile behavior:

- `sandbox_compute_and_store`: `airtable` is forbidden.
- `sandbox_network_restricted`: `airtable` can be enabled.

Use PATs scoped to least-privilege base/table permissions.

---

## 4. Verbs and syntax

### 4.1 Read verbs

- `list(table, params?)` -> `{records, offset?}`
- `find(table, formula_or_filter)` -> `{records, offset?}`
- `get_table(table)` -> `{table}`
- `list_tables()` -> `{tables}`
- `list_bases()` -> `{bases, offset?}`

### 4.2 Write verbs

- `create(table, record_or_records)`
- `update(table, record_or_records)`
- `delete(table, record_id_or_ids)`
- `upsert(table, key_field, key_value, fields)` -> `{ok, action, record}`

### 4.3 Attachment verbs (scoped)

- `attachment.upload(table, record_id, field_name, file_path_or_bytes_or_url, filename?)`
- `attachment.download(table, attachment_url, output_path?)`

Return shapes:

- upload -> `{ok, attachment|record}`
- download -> `{bytes_b64,size}` or `{path,size}`

### 4.4 Webhook verbs (basic)

- `webhook.create(table, table_or_view, actions, notification_url)`
- `webhook.list(table)`
- `webhook.delete(table, webhook_id)`

`webhook.create` returns registration metadata (`webhook_id`, expiration, MAC secret, specification). Payload ingestion/verification remains external in this pass.

Single-record shape:

- `{id, fields, createdTime}`

Batch shape:

- `{records: [...]}`

---

## 5. Validation and safety rules

- Mutating verbs require `allow_write=true`.
- Table allow-list is enforced when configured.
- Attachment and webhook verbs also respect table allow-list.
- URL-based attachment flows can be constrained by `allow_attachment_hosts`.
- Adapter retries transient HTTP failures and rate-limit responses with bounded backoff.
- Pass scope remains intentionally light (no schema ops, no deep webhook payload handling).

---

## 6. Connection behavior

- Uses Airtable REST API over HTTPS.
- Uses shared `httpx.Client` and async-compatible `httpx.AsyncClient` per adapter instance.
- PAT and base id are required for table/record operations.

Implementation reference:

- `adapters/airtable/adapter.py`

---

## 7. Limitations and roadmap

Current limitations:

- No schema mutation verbs in adapter.
- Webhook payload replay/verification helpers remain out-of-scope (registration lifecycle only).

Related docs:

- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/adapter_manifest.json`
- `tooling/security_profiles.json`

---

## 8. Running integration tests

By default, integration tests are skipped by the standard pytest profile (`-m 'not integration'`).

Direct API key mode:

```bash
export AINL_TEST_USE_AIRTABLE=1
export AINL_AIRTABLE_API_KEY='pat_xxx'
export AINL_AIRTABLE_BASE_ID='app_xxx'
export AINL_AIRTABLE_TEST_TABLE='users'
pytest -m integration tests/test_airtable_adapter_integration.py --airtable-api-key "$AINL_AIRTABLE_API_KEY" --airtable-base-id "$AINL_AIRTABLE_BASE_ID"
```

Make helper:

```bash
AINL_TEST_USE_AIRTABLE=1 \
AINL_AIRTABLE_API_KEY='pat_xxx' \
AINL_AIRTABLE_BASE_ID='app_xxx' \
AINL_AIRTABLE_TEST_TABLE='users' \
make airtable-it
```
