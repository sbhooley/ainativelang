# External executor bridge (HTTP)

**Status:** Contract and integration guidance. The **`http`** path uses the existing HTTP adapter; the optional **`bridge`** adapter (Phase 3) is **off by default** and only active when the host enables it — it does not change default **core-only** runs or IR semantics for programs that do not use `bridge.Post`.

**See also:** [`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md) describes **orchestrator → AINL** (discover, submit, run). This file describes **AINL → external workers** when the host uses a generic HTTP boundary.

---

## Integration preference (read this first)

**For OpenClaw / NemoClaw / ZeroClaw agents, prefer the existing MCP server (`ainl-mcp`).**  
That path is purpose-built for workflow-level integration with MCP-compatible hosts. Entrypoint: `scripts/ainl_mcp_server.py` (CLI: `ainl-mcp`). Exposure profiles: `tooling/mcp_exposure_profiles.json`. OpenClaw-oriented quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`. **OpenClaw** skill + **`ainl install-openclaw`** (`~/.openclaw/openclaw.json`): [`docs/OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md). **ZeroClaw** skill + `~/.zeroclaw/` bootstrap: [`docs/ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md).

**Use this HTTP bridge pattern for generic external executors** (Zapier-style webhooks, internal microservices, bespoke fan-out gateways, CI callbacks, or any worker that is not exposed as MCP). It is the **secondary** integration style relative to MCP for OpenClaw-family stacks (including **ZeroClaw** when using MCP).

---

## 1. Purpose

AINL’s runtime already delegates I/O to **allowlisted adapters**. The **`http`** adapter is the stable, canonical way to call out from a graph without adding new `R` syntax: build a JSON payload in the frame, then `R http.Post …` to a configured URL.

This document defines a **small JSON contract** so many backends (plugins, agents-as-a-service, internal tools) can sit behind **one or more HTTP endpoints** while AINL programs stay portable and deterministic at the graph level.

---

## 2. When to use the HTTP bridge

| Situation | Prefer |
|-----------|--------|
| OpenClaw / NemoClaw / ZeroClaw agent driving AINL tools from an MCP host | **MCP** (`ainl-mcp`) |
| Third-party SaaS, legacy REST service, internal queue worker | **HTTP bridge** (`http.Post` + contract below) |
| One gateway that fans out to N executor types | **HTTP bridge** (single URL; gateway routes by `executor` id) |

---

## 3. Request envelope (recommended)

**Machine-readable schema:** [`schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json) (JSON Schema 2020-12). Python helper: `schemas/executor_bridge_validate.validate_executor_bridge_request` (call from gateways or tests when you want a shared check).

**AINL reuse:** compile-time include [`modules/common/executor_bridge_request.ainl`](../../modules/common/executor_bridge_request.ainl) — set `ainl_bridge_request_json` to the JSON **text**, then `Call …/bridge_req/ENTRY` to parse once (see module header).

Hosts should accept a JSON body shaped like:

```json
{
  "run_id": "opaque-correlation-id",
  "step_id": "graph-node-or-label-hint",
  "executor": "string-executor-id",
  "payload": {},
  "timeout_s": 30
}
```

| Field | Meaning |
|-------|--------|
| `run_id` | Correlates logs across AINL runner, bridge, and worker. |
| `step_id` | Optional hint tying the call to a label or node in the IR (for tracing). |
| `executor` | Logical name the bridge maps to a concrete plugin/worker (fan-out routers use this). |
| `payload` | Executor-specific JSON; keep it serializable and bounded. |
| `timeout_s` | Hint for the worker; AINL-side `http` timeouts should still be set explicitly on the `R` step. |

Programs may omit fields the bridge does not need, but **stable names** help shared tooling.

---

## 4. Response envelope (align with `http` adapter)

Align with the monitoring-oriented **HTTP result envelope** described in [`docs/reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) (§ HTTP adapter — result envelope): executor-specific data lives in the decoded **body**; transport success/failure uses **`ok`**, **`status_code`**, **`error`**, etc., as returned by the runtime’s `http` adapter for that call.

Bridge implementations should return normal HTTP status codes (e.g. 2xx for handled requests, 4xx/5xx for client/server errors) so AINL graphs can branch on `resp` without special cases.

---

## 5. Configuration and security

- **Base URLs, API keys, and mTLS** belong in **host / runner configuration**, not in public example repos.
- Grant **`http`** (and the target host) only via **capability allowlists** on programs that need outbound calls (`capabilities.allow` in IR / runner policy).
- Treat bridge endpoints as **privileged**: authenticate, rate-limit, and validate `executor` against an allowlist on the server.
- **Request shape:** Prefer validating inbound JSON against [`schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json) (or call `schemas.executor_bridge_validate.validate_executor_bridge_request` from Python). A permissive pattern is to validate only when the decoded body is a **dict** and includes **`executor`** (so `llm.classify`-style bodies without that field stay loose).

---

## 6. Multi-backend support on the bridge

A single **bridge HTTP service** (one base URL that AINL calls with `http.Post` or `bridge.Post`) can **fan out** to many concrete workers. The contract field **`executor`** (or, with the optional `bridge` adapter, the configured executor key) is the stable routing key; the bridge maps it to an internal queue, RPC, second HTTP hop, or plugin process.

**Recommended properties of the bridge:**

- Maintain an **allowlisted** map `executor_id → backend` (reject unknown ids with 4xx).
- Keep **audit logs** keyed by `run_id` and `step_id` / `node_id` from the request envelope.
- Return responses that still follow the **HTTP result envelope** expected by the AINL `http` stack (§4).

**Example routing pseudocode (illustrative):**

```text
on POST /v1/execute:
  body = read_json()
  ex = body.executor
  if ex not in ROUTES: return 400
  backend = ROUTES[ex]   # e.g. URL, queue name, or handler id
  result = dispatch(backend, body.payload, deadline=body.timeout_s)
  return 200 with JSON body suitable for the client (and normal status codes on failure)
```

**Flask-shaped sketch (illustrative):** the same routing idea maps cleanly onto a small route table. This is **not** production-complete (auth, body size limits, structured errors, and real `dispatch` are omitted).

```python
# Illustrative Flask-shaped routing only — not production-complete.
from flask import Flask, request, jsonify

app = Flask(__name__)

# executor_id -> backend handle (downstream URL, queue name, plugin id, etc.)
ROUTES = {
    "plugin.alpha": "https://worker.internal/alpha",
    "plugin.beta": "queue:beta-jobs",
}


def dispatch(backend, payload, timeout_s):
    # Enqueue, second HTTP hop, or in-process handler; cap concurrency per route here.
    return {"echo": payload, "via": str(backend)}


@app.post("/v1/execute")
def bridge_execute():
    body = request.get_json(force=True, silent=False)
    if not isinstance(body, dict):
        return jsonify({"error": "expected JSON object"}), 400
    ex = body.get("executor")
    if ex not in ROUTES:
        return jsonify({"error": "unknown executor"}), 400
    out = dispatch(ROUTES[ex], body.get("payload"), body.get("timeout_s"))
    return jsonify(out), 200
```

AINL remains unaware of how many backends exist; it only sees one outbound call per step.

---

## 7. Resource contention & capacity

**On the bridge (operator responsibility):**

- Use a **queue** or job system when workers are slower than request arrival; cap **max concurrency** per executor and globally so a burst of AINL runs cannot exhaust workers or downstream APIs.
- Enforce **timeouts** on each backend call; surface failures as HTTP **5xx** or **4xx** consistently so graphs can branch or fail predictably.
- Apply **rate limits** at the bridge (and per-executor) to protect shared infrastructure.

**On the AINL side (built-in limits):**

- **`http` / `bridge` timeouts** — For **`ainl run`**, **`--http-timeout-s`** sets the **client-side** wait for each **`http.Post`** / **`bridge.Post`** (default **5** seconds). Executor JSON may carry a larger **`timeout_s`** for the **gateway’s** downstream call; if the **AINL client** gives up first, you still see a transport timeout. **LLM-heavy** graphs (e.g. OpenRouter classify) typically need **60–120+** seconds. The reference **`apollo-x-bot`** scripts use **120** and **`AINL_HTTP_TIMEOUT_S`**; see [`docs/reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) §2.4.3 and [`apollo-x-bot/README.md`](../../apollo-x-bot/README.md) (troubleshooting). Per-call **`timeout_s`** on **`R http.Post …`** (§2.1 slot schema) overrides the adapter default when provided.
- **`llm.classify` envelope vs legacy (gateways)** — If a worker implements both **legacy** classify (server builds prompts from **`tweets[]`**) and **envelope** classify (OpenAI-style **`messages[]`**), treat **envelope mode** as active only when **`messages`** is a **non-empty** list. A bare **`classify_response: "raw"`** (or similar) **without** **`messages`** should **not** force envelope handling or spurious **`envelope_missing_messages`** errors; fall back to legacy. Implemented in [`apollo-x-bot/gateway_server.py`](../../apollo-x-bot/gateway_server.py) (`_classify_wants_envelope`).
- **Graph resource ceilings** — `RuntimeEngine` in [`runtime/engine.py`](../../runtime/engine.py) enforces limits such as **`max_steps`**, **`max_depth`**, **`max_adapter_calls`**, **`max_time_ms`**, **`max_frame_bytes`** when set on the engine or via runner/MCP policy (see [`docs/operations/CAPABILITY_GRANT_MODEL.md`](../operations/CAPABILITY_GRANT_MODEL.md) for how grants merge **limits**, and the root [`README.md`](../../README.md) security overview for default conservative ceilings on runner/MCP surfaces).

Together, bridge-side queuing and AINL-side limits prevent a single workflow from spawning unbounded outbound work or tying up the runtime.

---

## 8. Progressive implementation (no breaking changes)

1. **Docs** (this file) — contract + MCP-first positioning.
2. **Examples** (Phase 1) — `examples/integrations/executor_bridge_min.ainl` posts a minimal envelope to `http://127.0.0.1:17300/v1/execute` (change for your environment). Local mock: `python3 scripts/mock_executor_bridge.py`. See `examples/integrations/README.md`. The sample branches with `X http_status get resp status` then `If http_status=200 ->…` so the condition matches graph-friendly `If` semantics (avoid raw `(core.ne resp.status …)` in the condition slot for graph-preferred runs).
3. **Tests** (Phase 2) — `tests/test_executor_bridge_integration.py` runs the Phase 1 example against an in-process HTTP mock (no live network, no manual `mock_executor_bridge.py`). **`tests/test_executor_bridge_envelope.py`** covers the schema helper. Optional: add an app-local integration test that drives your bridge gateway + main graph in dry-run mode.
4. **Optional `bridge` adapter** (Phase 3) — `R bridge.Post <executor_key> <body_var> ->resp` resolves `<executor_key>` to a URL via host config (`ainl run --enable-adapter bridge --bridge-endpoint key=URL`, or runner `adapters.bridge.endpoints`). Same response envelope as `http.Post`. See `docs/reference/ADAPTER_REGISTRY.md` §2.4 and `examples/integrations/executor_bridge_adapter_min.ainl`.
5. **Phase 4** (this document, §6–§7) — multi-backend fan-out, Flask-shaped routing sketch, capacity guidance, and explicit pointer to [`runtime/engine.py`](../../runtime/engine.py) for limit fields; no new language or runtime behavior.

None of these steps require changing the default **`core`-only** capability profile for existing programs.

---

## 9. Related links

- **Production-style layout:** App-local trees typically pair an **`ExecutorBridgeAdapter`** (or equivalent) with a small HTTP gateway, gateway-adjacent **`req_*` / main `.ainl` graphs** that compose [`modules/common/executor_request_builder.ainl`](../../modules/common/executor_request_builder.ainl) or [`modules/common/executor_bridge_request.ainl`](../../modules/common/executor_bridge_request.ainl), and **`.txt` prompts** beside the gateway. Optional reusable LLM `include` in [`modules/llm/`](../../modules/llm/README.md). Naming and boundaries: [`docs/language/AINL_CORE_AND_MODULES.md` §8](../language/AINL_CORE_AND_MODULES.md#8-repository-strict-include-libraries-ainl).
- **Schema & validation:** [`schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json), [`schemas/executor_bridge_validate.py`](../../schemas/executor_bridge_validate.py)
- **Graph execution note:** dotted `R core.*` steps pass the first operand through the frame resolver for `target` (so `core.PARSE` can consume a variable holding JSON text under graph-preferred execution); see `runtime/engine.py` (`_exec_r_call`).
- MCP server: `scripts/ainl_mcp_server.py`, `tooling/mcp_exposure_profiles.json`
- OpenClaw quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- External orchestration (host → AINL): `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- Adapter catalog: `docs/reference/ADAPTER_REGISTRY.md`, `tooling/adapter_manifest.json`
- Integration narrative: `docs/INTEGRATION_STORY.md`
