# AI Native Lang (AINL) Adapter Registry (AINL 1.0)

> **OpenClaw (MCP skill):** For **`skills/openclaw/`**, **`ainl install-openclaw`**, and **`~/.openclaw/openclaw.json`** MCP wiring, see **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)**.
>
> **ZeroClaw:** For the **ZeroClaw skill**, **`ainl install-zeroclaw`**, and **`~/.zeroclaw/`** MCP wiring, see **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)**. This catalog lists adapters for all hosts, including OpenClaw **extension** tiers (`extension_openclaw`, `ocl.*`, etc.).

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

The adapter also includes a **small built-in retry/backoff** layer:

- up to 3 total attempts (1 initial + 2 retries),
- exponential backoff with short delays between retries,
- retries only on transport-level failures (DNS/timeout/TLS) and 5xx server errors,
- **no retries** on 4xx client errors (those fail immediately).

---

## 2.4 Executor bridge adapter – `bridge` (optional)

- **name**: `bridge`
- **verbs**: `Post`
- **effect**: `io-write` (network); delegates to the same stack as `http.Post`
- **when to use**: Host supplies a **table of executor id → URL** (CLI `--bridge-endpoint` or runner `adapters.bridge.endpoints`). Programs call `R bridge.Post <executor_key> <body_var> ->resp` instead of embedding URLs in source. See `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` for the recommended **request envelope** (JSON Schema: `schemas/executor_bridge_request.schema.json`; AINL helper: `modules/common/executor_bridge_request.ainl`).

### 2.4.1 Slot schema

```text
R bridge.Post executor_key body_var ->resp
```

- `executor_key`: string token matching a configured map entry (not a URL).
- `body_var`: frame var with JSON-serializable object (same as `http.Post` body).
- `resp`: same **result envelope** as `http` (§2.3).

### 2.4.2 Enablement

- **CLI**: `ainl run program.ainl --enable-adapter bridge --bridge-endpoint my.exec=https://.../v1/execute` (repeatable).
- **Runner service**: `adapters.enable` includes `"bridge"` and `adapters.bridge.endpoints` is set.

### 2.4.3 Client timeout (`ainl run`)

The **`bridge`** adapter uses the same **`SimpleHttpAdapter`** stack as **`http`**. For **`ainl run`**, per-request waits are controlled by **`--http-timeout-s`** (CLI default **5** seconds). Slow backends — batched **LLM** calls, OpenRouter, fan-out gateways that block until a worker finishes — usually need **60–180** seconds on the client or the runtime will report a **transport timeout** while the server is still working.

**Reference:** [`apollo-x-bot/openclaw-poll.sh`](../../apollo-x-bot/openclaw-poll.sh) and [`apollo-x-bot/run-with-gateway.sh`](../../apollo-x-bot/run-with-gateway.sh) pass **`--http-timeout-s 120`** and honor **`AINL_HTTP_TIMEOUT_S`**. See also [`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](../integrations/EXTERNAL_EXECUTOR_BRIDGE.md) §7.

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

For the current OpenClaw monitors, only queue `"notify"` is implemented. Its consumer is **formatter‑driven and tolerant**: payloads are typically objects that include fields like `email_count`, `cal_count`, `social_count`, `leads_count`, `health_score`, `failed_services`, and `ts`, but this shape is **advisory rather than a strict schema**. Downstream formatters handle missing or extra fields defensively.

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

- `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`

---

## 6. Adapter manifest (machine‑readable catalog and tiers)

For small‑model training and automation, the **canonical machine‑readable source** is:

- `tooling/adapter_manifest.json`

That file now describes the full adapter surface, including:

- `core`, `db`, `api`, `email`, `calendar`, `social`, `ext`,
- `wasm`, `cache`, `queue`, `txn`, `auth`,
- `http`, `sqlite`, `fs`, `tools`,
- `svc`, `extras`, `agent`, `tiktok`, `web`, `memory`.

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
    // ... more adapters ...
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

## 8. Agent coordination adapter – `agent` (extension / OpenClaw, advanced)

- **name**: `agent`
- **verbs**: `send_task, read_result`
- **support_tier**: `extension_openclaw`
- **lane**: non-canonical; OpenClaw-only extension adapter
- **intended audience**: advanced operators building local coordination loops;
  **not** a safe default for unsupervised agents.

The `agent` adapter provides a **minimal, local, file-backed** substrate for
exchanging `AgentTaskRequest` and `AgentTaskResult` envelopes as defined in
`docs/advanced/AGENT_COORDINATION_CONTRACT.md`. It does **not** implement a swarm engine
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

---

## 9. Summary of additional adapters (see manifest and registry)

The following adapters are fully specified in `tooling/adapter_manifest.json`
and `ADAPTER_REGISTRY.json` but do not require long-form slot schemas here:

- **`core`** (tier: `core`, lane: `canonical`): arithmetic, string, JSON, time, and environment helpers (`ADD`, `SUB`, `MUL`, `DIV`, `IDIV`, `MIN`, `MAX`, `CONCAT`, `SPLIT`, `JOIN`, `LOWER`, `UPPER`, `SUBSTR`, `ENV`, `PARSE`, `STRINGIFY`, `NOW`, `ISO`, `SLEEP`, `ECHO`). `IDIV` performs integer division (truncates toward zero). `SUBSTR` takes `(s, start, length)`. `ENV` reads `os.environ` (`ENV name` or `ENV name default`). In X expressions, these are also available as lowercase `core.*` aliases (e.g. `core.add`, `core.idiv`, `core.substr`, `core.env`).
- **`api`** (tier: `compatibility`, lane: `noncanonical`): legacy HTTP/API surface used by older step‑list forms (`G`, `P`, `POST`).
- **`sqlite`** (tier: `core`, lane: `canonical`): direct SQLite access (`Execute`, `Query`) with allow‑list and timeout controls.
- **`fs`** (tier: `core`, lane: `canonical`): sandboxed filesystem operations (`Read`, `Write`, `List`, `Delete`) with size and extension guards.
- **`tools`** (tier: `core`, lane: `canonical`): bridge to external tool calls (`Call`) as defined in `docs/reference/TOOL_API.md`.
- **`txn`** (tier: `core`, lane: `canonical`): transaction namespace (`Begin`, `Commit`, `Rollback`) on supported backends.
- **`auth`** (tier: `core`, lane: `canonical`): authentication namespace (`Validate`) wired into service middleware.
- **`email`**, **`calendar`**, **`social`** (tier: `extension_openclaw`, lane: `canonical`): OpenClaw monitoring adapters for unread email, upcoming calendar events, and social/web mentions.
- **`ext`** (tier: `compatibility`, lane: `noncanonical`): test‑only external extension namespace used in runtime tests.
- **`tiktok`** (tier: `extension_openclaw`, lane: `noncanonical`): TikTok/CRM reporting surface (`F`, `recent`, `videos`) for OpenClaw monitors. `recent` verb retrieves recent posts/metrics with a configurable limit.
- **`web`** (tier: `extension_openclaw`, lane: `noncanonical`): web search surface (`search`) backed by OpenRouter/Perplexity. Usage: `R web.search "query string" ->results`. Requires `OPENROUTER_API_KEY` env var; returns a list of result objects with `title`, `url`, `snippet`.
- **`memory`** (tier: `extension_openclaw`, lane: `noncanonical`): explicit memory adapter (`put`, `get`, `append`, `list`, `delete`, `prune`) as specified in `docs/adapters/MEMORY_CONTRACT.md`. Supported namespaces include `ops` (in addition to `session`, `long_term`, `daily_log`, `workflow`). The CLI registers a default **`memory`** adapter when running programs that use `record_decision`-style includes even if `--enable-adapter memory` is omitted (see `cli/main.py`).
- **`vector_memory`** (tier: `compatibility`, lane: `noncanonical`): local JSON-backed store with keyword-overlap scoring — verbs **`SEARCH`**, **`LIST_SIMILAR`**, **`UPSERT`**. Implementation: `adapters/vector_memory.py`. Env: **`AINL_VECTOR_MEMORY_PATH`** (default `.ainl_vector_memory.json` in cwd). Enable: `--enable-adapter vector_memory`.
- **`tool_registry`** (tier: `compatibility`, lane: `noncanonical`): local JSON tool catalog — verbs **`LIST`**, **`GET`**, **`REGISTER`**, **`DISCOVER`**. Implementation: `adapters/tool_registry.py`. Env: **`AINL_TOOL_REGISTRY_PATH`** (default `.ainl_tool_registry.json` in cwd). Enable: `--enable-adapter tool_registry`.
- **`langchain_tool`** (tier: `compatibility`, lane: `noncanonical`): bridge for **LangChain / CrewAI-style** tools registered in-process — use **`R langchain_tool.CALL "tool_name" <args...> -> out`** (strict-friendly) or **`R langchain_tool.my_search_tool "query" -> out`** for the built-in demo stub / registered name matching the verb. Returns an envelope **`{ok, tool, result}`**. Implementation: `adapters/langchain_tool.py`; **`langchain-core`** is optional. Enable: `--enable-adapter langchain_tool`. Register tools from Python via **`register_langchain_tool(name, tool)`** before `run`.

For exact argument lists, effect metadata, and envelopes, treat
`tooling/adapter_manifest.json` as the source of truth and
`ADAPTER_REGISTRY.json` as the operator‑level view.
