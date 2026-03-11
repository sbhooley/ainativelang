# AI Native Lang (AINL) Adapter Registry (v0.9)

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
- **verbs**: `Get`, `Post`
- **effect**: `io-read` (GET), `io-write` (POST)

### 2.1 Slot schema

```text
R http.Get /path_or_url ->resp
R http.Post /path_or_url body_var ->resp
```

- `/path_or_url`: either an absolute URL or a service‑relative path.
- `body_var`: frame var containing JSON‑serializable body.
- `resp`: frame variable receiving the decoded response.

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

---

## 6. Adapter manifest (machine‑readable sketch and tiers)

For small‑model training you can treat this as the canonical manifest:

```json
{
  "db": {
    "verbs": ["F", "C", "U", "D"],
    "effects": { "F": "io-read", "C": "io-write", "U": "io-write", "D": "io-write" }
  },
  "http": {
    "verbs": ["Get", "Post"],
    "effects": { "Get": "io-read", "Post": "io-write" }
  },
  "cache": {
    "verbs": ["Get", "Set"],
    "effects": { "Get": "io-read", "Set": "io-write" }
  },
  "queue": {
    "verbs": ["Put"],
    "effects": { "Put": "io-write" }
  }
}
```

This manifest matches the behavior enforced by `tooling/effect_analysis.py` and the runtime adapters.

In the full `tooling/adapter_manifest.json`, each adapter also carries lightweight
classification metadata:

- `support_tier`: `core` \| `extension_openclaw` \| `compatibility`
- `strict_contract`: `true` if the adapter/verbs are covered by the current strict
  adapter/effect validation (`ADAPTER_EFFECT`), `false` otherwise
- `recommended_lane`: `canonical` \| `noncanonical` to distinguish the preferred
  canonical lane from accepted-but-noncanonical surfaces

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

## 8. Agent coordination adapter – `agent` (extension / OpenClaw)

- **name**: `agent`
- **verbs**: `send_task`, `read_result`
- **support_tier**: `extension_openclaw`
- **lane**: non-canonical; OpenClaw-only extension adapter

The `agent` adapter provides a **minimal, local, file-backed** substrate for
exchanging `AgentTaskRequest` and `AgentTaskResult` envelopes as defined in
`docs/AGENT_COORDINATION_CONTRACT.md`. It does **not** implement a swarm engine
or remote federation.

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

