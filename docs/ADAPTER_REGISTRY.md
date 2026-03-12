# AI Native Lang (AINL) Adapter Registry (AINL 1.0)

This document describes the **small‑model‑friendly adapter set** exposed by this implementation. It is a human + machine readable catalog for agents.

The machine-readable source of truth is:

- `tooling/adapter_manifest.json`

Tests enforce consistency between that manifest and effect analysis:

- `tests/test_adapter_manifest.py`

For each adapter we specify:

- **name**: canonical adapter name.
- **verbs**: supported operations.
- **effect**: `io-read`, `io-write`, or `io`.
- **inputs**: slots and expected types.
- **outputs**: variables populated in the frame.
- **examples**: canonical `R` statements.

The same information can be exported as JSON from this document if needed.

---

## 1. Database adapter – `db`

- **name**: `db`
- **verbs**: `F` (find), `C` (create), `U` (update), `D` (delete)
- **effect**: `io-read` for `F`, `io-write` for `C/U/D`

### 1.1 Slot schema

```text
R db.F Entity filter ->out
R db.C Entity payload ->out
R db.U Entity filter payload ->out
R db.D Entity filter ->out
```

- `Entity`: identifier (e.g. `User`, `Order`).
- `filter`: expression or `*` for all.
- `payload`: expression or `*` for passthrough.
- `out`: frame variable that will hold the result.

### 1.2 Examples

```text
# Find all users
R db.F User * ->users

# Create a user (payload usually expanded by the compiler)
R db.C User * ->created_user
```

---

## 2. HTTP adapter – `http`

- **name**: `http`
- **verbs (runtime namespace)**: `Get`, `Post`, `Put`, `Patch`, `Delete`, `Head`, `Options`
- **canonical effects**: `io-read` for `Get`/`Head`/`Options`, `io-write` for `Post`/`Put`/`Patch`/`Delete`

### 2.1 Slot schema (AINL `R` surface)

```text
R http.Get /path_or_url [headers_var] [timeout_s] ->resp
R http.Post /path_or_url body_var [headers_var] [timeout_s] ->resp
R http.Put /path_or_url body_var [headers_var] [timeout_s] ->resp
R http.Patch /path_or_url body_var [headers_var] [timeout_s] ->resp
R http.Delete /path_or_url [headers_var] [timeout_s] ->resp
R http.Head /path_or_url [headers_var] [timeout_s] ->resp
R http.Options /path_or_url [headers_var] [timeout_s] ->resp
```

- `/path_or_url`: either an absolute URL or a service‑relative path.
- `body_var`: frame var containing JSON‑serializable body (for `Post`/`Put`/`Patch`).
- `headers_var`: optional frame var containing a string‑keyed dict of headers.
- `timeout_s`: optional float seconds override; defaults come from the adapter config.
- `resp`: frame variable receiving the normalized response envelope.

### 2.2 Examples

```text
# Fetch users from an external API
R http.Get "https://api.example.com/users" ->resp

# Post metrics to webhook
R http.Post "https://hook.example.com/metrics" metrics ->ack
```

### 2.3 Result envelope (monitoring contract)

For monitoring-oriented flows, the `http` adapter is described as returning a **result envelope** with these fields:

- `ok: bool` — true if the HTTP call completed and the status code is considered successful (e.g. 2xx).
- `status_code: int|null` — HTTP status code if a response was received; `null` on pure transport error.
- `error: str|null` — transport-level error description (DNS failure, timeout, TLS error, etc.); `null` if none.
- `body: any` — decoded response body (string/JSON/etc.), as today.
- `headers: dict|none` — optional response headers, when available.
- `url: str` — URL/path that was called (for correlation).

This envelope is **descriptive metadata only** in this pass; it does not change current adapter behavior. Future monitoring patterns and agents can treat these fields as the canonical monitoring contract once runtime normalization is implemented.

---

## 3. Cache adapter – `cache`

- **name**: `cache`
- **verbs**: `Get`, `Set`
- **effect**: `io-read` / `io-write`

### 3.1 Slot schema

```text
R cache.Get key ->value
R cache.Set key value ttl_s ->ok
```

- `key`: string key.
- `value`: any JSON‑serializable value.
- `ttl_s`: integer seconds.

### 3.2 Examples

```text
R cache.Get "users:all" ->users_cache
R cache.Set "users:all" users 60 ->ok
```

---

## 4. Queue adapter – `queue`

- **name**: `queue`
- **verbs**: `Put`
- **effect**: `io-write`

### 4.1 Slot schema

```text
R queue.Put queue_name payload ->msg_id
```

- `queue_name`: identifier or string.
- `payload`: frame var.

### 4.2 Example

```text
R queue.Put "emails" email_job ->msg_id
```

### 4.3 Result envelope (monitoring contract)

For monitoring, the `queue` adapter is described as returning a **result envelope** with these fields:

- `ok: bool` — true if the enqueue operation reached the underlying queue backend successfully.
- `message_id: str|null` — backend-assigned message identifier, if available.
- `queue_name: str` — queue name used for the call.
- `error: str|null` — error description if enqueue failed at the adapter/backend layer.

As with `http`, this envelope is **descriptive metadata only** for now and does not alter current adapter return behavior. Existing examples may continue to ignore the result (`->_`) safely.

---

## 5. Service health adapter – `svc` (extension / OpenClaw)

- **name**: `svc`
- **verbs**: `caddy`, `cloudflared`, `maddy`, `crm`
- **support_tier**: `extension_openclaw`
- **lane**: non-canonical; OpenClaw-only extension adapter

The `svc` adapter is used by OpenClaw examples to surface basic service health information.

### 5.1 Result envelope (health contract, extension-only)

For OpenClaw environments, the `svc` adapter is described as returning a **health envelope** with these fields:

- `ok: bool` — true if the service is considered healthy enough under its own policy.
- `status: str` — status string such as `"up"`, `"down"`, `"degraded"`, or `"unknown"`.
- `latency_ms: int|null` — optional latency measurement in milliseconds, when available.
- `error: str|null` — error description if probing the service fails (e.g. health endpoint unreachable).

This is an **extension/OpenClaw-only contract** and is **not** part of the canonical AINL core. It is intended for monitoring and agent reasoning in OpenClaw deployments and is documented here for clarity; current runtime behavior is unchanged in this pass.

For safety and threat-model guidance on extension adapters and coordination, see
also:

- `docs/SAFE_USE_AND_THREAT_MODEL.md`

---

## 6. Adapter manifest (machine‑readable catalog and tiers)

For small‑model training and automation, the **canonical machine‑readable source** is:

- `tooling/adapter_manifest.json`

That file now describes the full adapter surface, including:

- `core`, `db`, `api`, `email`, `calendar`, `social`, `ext`,
- `wasm`, `cache`, `queue`, `txn`, `auth`,
- `http`, `sqlite`, `fs`, `tools`,
- `svc`, `extras`, `agent`, `tiktok`, `memory`.

Each adapter entry carries:

- `verbs`: list of supported verbs/targets.
- `effect_default`: canonical default effect (`pure` \| `io`).
- `support_tier`: `core` \| `extension_openclaw` \| `compatibility`.
- `strict_contract`: `true` if covered by strict adapter/effect validation, else `false`.
- `recommended_lane`: `canonical` \| `noncanonical` to distinguish preferred canonical lanes from accepted-but-noncanonical surfaces.
- Optional `result_envelope` metadata for monitoring‑oriented adapters (e.g. `http`, `queue`, `svc`).

A **partial sketch** of the manifest shape (not exhaustive) looks like:

```json
{
  "adapters": {
    "db": {
      "support_tier": "core",
      "strict_contract": true,
      "recommended_lane": "canonical",
      "verbs": ["F", "G", "P", "C", "U", "D"],
      "effect_default": "io"
    },
    "http": {
      "support_tier": "core",
      "strict_contract": true,
      "recommended_lane": "canonical",
      "verbs": ["Get", "Post", "Put", "Patch", "Delete", "Head", "Options"],
      "effect_default": "io",
      "result_envelope": {
        "fields": {
          "ok": "bool",
          "status_code": "int|null",
          "error": "str|null",
          "body": "any",
          "headers": "dict|none",
          "url": "str"
        }
      }
    }
    // ... other adapters ...
  }
}
```

`ADAPTER_REGISTRY.json` is a richer OpenClaw/operator-facing view (descriptions,
targets, config, side-effect notes). The overlapping adapter names/verbs are
validated against `tooling/adapter_manifest.json` by
`tests/test_adapter_registry_alignment.py` so they cannot silently diverge.

---

## 7. Extras adapter – `extras` (extension / OpenClaw)

- **name**: `extras`
- **verbs**: `file_exists`, `docker_image_exists`, `http_status`, `newest_backup_mtime`, `metrics`
- **support_tier**: `extension_openclaw`
- **lane**: non-canonical; OpenClaw-only extension adapter

The `extras` adapter provides utility health checks and a small metrics view for
OpenClaw-oriented monitors:

- `file_exists`: check whether a given path exists and is executable (returns `1`/`0`).
- `docker_image_exists`: check whether a Docker image exists locally (returns `1`/`0`).
- `http_status`: return an HTTP status code for a URL (best-effort, returns `0` on failure).
- `newest_backup_mtime`: return the newest `.bak` file mtime in a directory as an integer timestamp (or `0` if none).
- `metrics`: read a **precomputed JSON summary** file and expose a small metrics envelope.

### 7.1 `metrics` verb (summary-based metrics, extension-only)

`extras.metrics` is an **extension/OpenClaw-only observability helper**. It is:

- **read-only** over the filesystem,
- **sandboxed** to a summary root directory,
- **not** part of the canonical AINL core or strict contract.

Configuration and behavior:

- The sandbox root is taken from `AINL_SUMMARY_ROOT` (environment variable), defaulting to:
  - `/tmp/ainl_summaries`
- The `summary_path` argument is interpreted as a **relative path** under this root.
- Any attempt to escape the sandbox (e.g. `../..`) results in an `AdapterError`.

Expected input:

- A JSON file produced by tools such as `scripts/summarize_runs.py` with at least:
  - `run_count: int`
  - `ok_count: int`
  - `error_count: int`
  - `runtime_versions: [str]`
  - `result_kinds: {type: count}`
  - `trace_op_counts: {op: count}`
  - `label_counts: {label: count}`
  - `timestamps_present: bool`

Returned envelope:

- `run_count: int`
- `ok_count: int`
- `error_count: int`
- `ok_ratio: float|null` — `ok_count / run_count` when `run_count > 0`, otherwise `null`
- `runtime_versions: [str]`
- `result_kinds: {str: int}`
- `trace_op_counts: {str: int}`
- `label_counts: {str: int}`
- `timestamps_present: bool`

Failure modes:

- missing or unreadable file → `AdapterError("metrics failed to read ...")`
- invalid JSON → `AdapterError("metrics failed to read ...")`
- JSON top-level not an object → `AdapterError("metrics expects JSON object summary")`

As with other `extras` verbs, this adapter is intended for OpenClaw monitors and
agents; it does **not** change core language or runtime semantics.

---

## 9. Summary of additional adapters (see manifest and registry)

The following adapters are fully specified in `tooling/adapter_manifest.json`
and `ADAPTER_REGISTRY.json` but do not require long-form slot schemas here:

- **`core`** (tier: `core`, lane: `canonical`): arithmetic, string, JSON, and time helpers (`ADD`, `SUB`, `MUL`, `DIV`, `MIN`, `MAX`, `CONCAT`, `SPLIT`, `JOIN`, `LOWER`, `UPPER`, `PARSE`, `STRINGIFY`, `NOW`, `ISO`, `SLEEP`, `ECHO`).
- **`api`** (tier: `compatibility`, lane: `noncanonical`): legacy HTTP/API surface used by older step‑list forms (`G`, `P`, `POST`).
- **`sqlite`** (tier: `core`, lane: `canonical`): direct SQLite access (`Execute`, `Query`) with allow‑list and timeout controls.
- **`fs`** (tier: `core`, lane: `canonical`): sandboxed filesystem operations (`Read`, `Write`, `List`, `Delete`) with size and extension guards.
- **`tools`** (tier: `core`, lane: `canonical`): bridge to external tool calls (`Call`) as defined in `docs/TOOL_API.md`.
- **`txn`** (tier: `core`, lane: `canonical`): transaction namespace (`Begin`, `Commit`, `Rollback`) on supported backends.
- **`auth`** (tier: `core`, lane: `canonical`): authentication namespace (`Validate`) wired into service middleware.
- **`email`**, **`calendar`**, **`social`** (tier: `extension_openclaw`, lane: `canonical`): OpenClaw monitoring adapters for unread email, upcoming calendar events, and social/web mentions.
- **`ext`** (tier: `compatibility`, lane: `noncanonical`): test‑only external extension namespace used in runtime tests.
- **`tiktok`** (tier: `extension_openclaw`, lane: `noncanonical`): TikTok/CRM reporting surface (`F`, `recent`, `videos`) for OpenClaw monitors.
- **`memory`** (tier: `extension_openclaw`, lane: `noncanonical`): explicit memory adapter (`put`, `get`, `append`, `list`) as specified in `docs/MEMORY_CONTRACT.md`.

For exact argument lists, effect metadata, and envelopes, treat
`tooling/adapter_manifest.json` as the source of truth and
`ADAPTER_REGISTRY.json` as the operator‑level view.

---

## 8. Agent coordination adapter – `agent` (extension / OpenClaw, advanced)

- **name**: `agent`
- **verbs**: `send_task`, `read_result`
- **support_tier**: `extension_openclaw`
- **lane**: non-canonical; OpenClaw-only extension adapter
- **intended audience**: advanced operators building local coordination loops;
  **not** a safe default for unsupervised agents.

The `agent` adapter provides a **minimal, local, file-backed** substrate for
exchanging `AgentTaskRequest` and `AgentTaskResult` envelopes as defined in
`docs/AGENT_COORDINATION_CONTRACT.md`. It does **not** implement a swarm engine
or remote federation, and it should be treated as an **advanced, opt-in**
coordination surface rather than a general-purpose production control plane.

### 8.1 `send_task` verb (append AgentTaskRequest to JSONL)

`agent.send_task` expects:

- first argument: a JSON object matching `AgentTaskRequest` (or a compatible
  subset).

Behavior:

- resolves the sandbox root from `AINL_AGENT_ROOT` (default:
  `/tmp/ainl_agents`),
- computes the target file path as `root / rel_path`,
- rejects any attempt to escape the root (e.g. `../..`) with an `AdapterError`,
- JSON-serializes the envelope and appends it as a single line to the target
  file (JSONL format).

Return value:

- `task_id: str` — copied from `envelope["task_id"]` when present, else empty string.

This verb is intended as a **thin bridge** between AINL-based monitors and an
external orchestrator that reads `AgentTaskRequest` lines from the JSONL file.

### 8.2 `read_result` verb (read AgentTaskResult JSON)

`agent.read_result` expects:

- first argument: a `task_id` string.

Behavior:

- resolves the sandbox root from `AINL_AGENT_ROOT` (default:
  `/tmp/ainl_agents`),
- computes the target file path as `root / rel_path`,
- rejects any attempt to escape the root with an `AdapterError`,
- reads the target file and parses it as JSON,
- requires the top-level JSON value to be an object.

Return value:

- the parsed JSON object (compatible with `AgentTaskResult`).

Failure modes:

- missing or non-file path → `AdapterError("agent.read_result target does not exist")`
- invalid JSON → `AdapterError("agent.read_result failed to parse JSON: ...")`
- top-level value not an object → `AdapterError("agent.read_result expects JSON object result")`

This verb is a **local-only, read-only helper** for consuming previously written
result artifacts (for example, results emitted by an external orchestrator). It
does not change core AINL semantics and should be treated as an OpenClaw-specific
extension surface.

For cross-tool (Cursor ↔ OpenClaw) coordination, the **only** shared protocol
surface in this adapter is the combination of `send_task` and `read_result`.
Any additional verbs present in a specific OpenClaw deployment (such as
discovery or task-reading helpers) are extension-specific and are **not** part
of the agreed shared protocol.

