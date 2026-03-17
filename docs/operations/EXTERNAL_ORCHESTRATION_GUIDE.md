## External Orchestration Guide

**Status:** This document does not change compiler or runtime semantics. It
describes how external orchestrators can discover, configure, and use an AINL
runtime instance.

---

## 1. Purpose

This guide explains how an **external orchestrator** — a container platform,
sandbox controller, managed agent host, CI/CD system, or custom workflow
engine — can integrate with the AINL runtime.

It covers:

- capability discovery,
- workflow submission (source and pre-compiled IR),
- optional policy-gated execution,
- the responsibility boundary between AINL and the hosting environment,
- optional advanced layers (memory, coordination).

This guide is **framework-agnostic**. It applies equally to any orchestrator,
including NemoClaw, OpenShell, OpenClaw, Kubernetes-based platforms, and custom
hosts.

---

## 2. Architecture at a glance

```
┌──────────────────────────────────────────────┐
│  External orchestrator                       │
│  (sandbox controller / agent host / CI)      │
│                                              │
│  1. GET  /capabilities   →  discover         │
│  2. POST /run            →  execute          │
│     (optional: policy, limits, adapters)      │
│  3. GET  /health         →  liveness         │
│  4. GET  /ready          →  readiness        │
│  5. GET  /metrics        →  observability    │
└───────────────────┬──────────────────────────┘
                    │ HTTP
┌───────────────────▼──────────────────────────┐
│  AINL Runner Service                         │
│  (containerized or sidecar)                  │
│                                              │
│  ┌─────────────┐  ┌──────────────────────┐   │
│  │ Compiler    │  │ RuntimeEngine        │   │
│  │ (source→IR) │→ │ (graph execution)    │   │
│  └─────────────┘  └──────┬───────────────┘   │
│                          │                   │
│              ┌───────────▼───────────────┐   │
│              │ AdapterRegistry           │   │
│              │ (allowlisted adapters)    │   │
│              └───────────────────────────┘   │
└──────────────────────────────────────────────┘
```

The orchestrator is the control plane. The AINL runtime is the workflow
execution layer.

---

## 3. Step 1 — Discover capabilities

Before submitting workflows, the orchestrator can query the runtime to
understand what it supports.

```
GET /capabilities
```

Response:

```json
{
  "schema_version": "1.0",
  "runtime_version": "1.0.0",
  "policy_support": true,
  "adapters": {
    "core": {
      "support_tier": "core",
      "verbs": ["ADD", "SUB", "MUL", "CONCAT", "NOW", "..."],
      "effect_default": "pure",
      "recommended_lane": "canonical"
    },
    "http": {
      "support_tier": "core",
      "verbs": ["Get", "Post", "Put", "Delete", "..."],
      "effect_default": "io",
      "recommended_lane": "canonical"
    }
  }
}
```

Key fields for orchestrators:

| Field | Meaning |
|-------|---------|
| `runtime_version` | The version of the AINL runtime |
| `policy_support` | Whether the `/run` endpoint accepts an optional `policy` object |
| `adapters` | Map of available adapter namespaces with verbs, tiers, default effect, and lane |
| `adapters[name].support_tier` | `core` (canonical), `compatibility`, or `extension_openclaw` |
| `adapters[name].recommended_lane` | `canonical` or `noncanonical` |
| `adapters[name].privilege_tier` | Privilege tier hint such as `pure`, `local_state`, `network`, or `operator_sensitive` |

The orchestrator can use this information to:

- verify the runtime supports the adapters a workflow needs,
- populate a UI or policy engine with available capabilities,
- decide whether to submit a workflow or reject it before submission.

---

## 4. Step 2 — Submit a workflow

The orchestrator submits a workflow to `POST /run`. Two input modes are
supported.

### 4.1 Source code input

The orchestrator sends AINL source. The runner compiles it to IR and executes.

```json
{
  "code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x",
  "strict": true
}
```

### 4.2 Pre-compiled IR input

The orchestrator compiles AINL to IR separately (e.g. in a trusted build
step) and sends the IR directly. This separates compilation from execution.

```json
{
  "ir": {
    "ir_version": "1.0",
    "nodes": [ "..." ],
    "edges": [ "..." ]
  }
}
```

### 4.3 Configuration fields

| Field | Required | Purpose |
|-------|----------|---------|
| `code` | One of `code`/`ir` | AINL source to compile and execute |
| `ir` | One of `code`/`ir` | Pre-compiled IR to execute directly |
| `strict` | No (default `true`) | Strict-mode compilation |
| `label` | No | Entry label (defaults to first label) |
| `frame` | No | Initial variable frame |
| `limits` | No | Runtime resource limits object |
| `allowed_adapters` | No | Adapter allowlist (array of adapter names) |
| `adapters` | No | Per-adapter configuration (enable, host lists, paths, etc.) |
| `policy` | No | Policy object for pre-execution IR validation |
| `trace` | No | Include execution trace in response |
| `record_calls` | No | Record adapter calls for replay |
| `replay_log` | No | Replay from recorded adapter calls |

### 4.4 Successful response

```json
{
  "ok": true,
  "trace_id": "...",
  "label": "L1",
  "out": "...",
  "runtime_version": "1.0.0",
  "ir_version": "1.0",
  "duration_ms": 12.5,
  "adapter_p95_ms": { "core": 0.02 }
}
```

---

## 5. Step 3 — Optional policy-gated execution

If the orchestrator needs to restrict what a workflow can do, it includes a
`policy` object in the `/run` request. The runner validates the compiled IR
against the policy **before execution**. If the IR violates the policy, the
runner responds with HTTP 403 and does not execute.

### 5.1 Policy shape

```json
{
  "policy": {
    "forbidden_adapters": ["http", "fs", "agent"],
    "forbidden_effects": ["io-write"],
    "forbidden_effect_tiers": ["network"],
    "forbidden_privilege_tiers": ["network", "operator_sensitive"]
  }
}
```

All policy fields are optional. An empty `policy` object (`{}`) applies no
restrictions.

### 5.2 Policy rejection response (HTTP 403)

```json
{
  "ok": false,
  "trace_id": "...",
  "error": "policy_violation",
  "policy_errors": [
    {
      "code": "POLICY_ADAPTER_FORBIDDEN",
      "message": "Adapter 'http' is forbidden by policy",
      "data": { "label_id": "1", "node_id": "n1", "adapter": "http" }
    }
  ]
}
```

### 5.3 When policy is omitted

If the `policy` field is not present in the request, execution proceeds
without any policy check. This preserves backward compatibility.

### 5.4 Orchestrator-side vs runtime-side policy

The `/run` policy is a **pre-execution gate** at the runner service boundary.
It does not replace orchestrator-side policy. Orchestrators that have their
own policy engines can:

- apply their own checks before submitting to the runner (faster rejection),
- pass a `policy` object to the runner as defense-in-depth,
- or do both.

---

## 6. Responsibility boundary

The AINL runtime is a **workflow execution layer**. The table below clarifies
what AINL provides vs what the orchestrator must provide.

| Concern | AINL provides | Orchestrator provides |
|---------|--------------|----------------------|
| Workflow compilation | Compiler (source → IR) | Decides when/what to compile |
| Deterministic graph execution | RuntimeEngine | Decides when to invoke |
| Adapter capability gating | Allowlist via `AdapterRegistry` | Chooses which adapters to allow |
| Runtime resource limits | `max_steps`, `max_depth`, `max_time_ms`, etc. | Sets container-level CPU/memory/timeout |
| Pre-execution policy validation | Optional `policy` on `/run` | Defines the policy to apply |
| Capability discovery | `GET /capabilities` | Queries and acts on capabilities |
| Container isolation | No | Process, filesystem, network isolation |
| Secret management | No | Inject secrets via env or sidecar |
| Authentication/TLS | No | Reverse proxy, ingress, mTLS |
| Multi-tenant isolation | No | One instance per tenant, or orchestrator-level isolation |
| Coordination routing | No (file-backed mailbox only) | Routing, scheduling, retries, escalation |
| Log aggregation | Structured JSON to stdout | Pipeline to logging system |
| Approval workflows | Advisory envelope fields only | Enforce approval, budget, policy rules |

Named security profiles in `tooling/security_profiles.json` (for example
`local_minimal`, `sandbox_compute_and_store`, `sandbox_network_restricted`,
`operator_full`) can be used by orchestrators as **inputs** when choosing:

- which adapters to allow or forbid (`adapter_allowlist`, `forbidden_adapters`),
- which privilege tiers to disallow (`forbidden_privilege_tiers`),
- which runtime limits to apply.

These profiles are packaging/guidance artifacts only; they do not change the
behavior of `/run` and do not replace real sandboxing, network policy, or
enterprise security controls.

---

## 7. Optional advanced layers

AINL manages state through explicit, tiered adapters rather than hiding state
in prompt history. For a full description of the state model, see
`docs/architecture/STATE_DISCIPLINE.md`.

The tiers most relevant to orchestrated environments are:

- **Frame** (Tier 1) — ephemeral variables within a single run (always available)
- **Cache** (Tier 2) — short-lived key-value entries with optional TTL
- **Memory / SQLite / FS** (Tier 3) — durable persistence across runs
- **Queue / Agent** (Tier 4) — cross-workflow and cross-agent coordination

### 7.1 Memory

The AINL memory adapter provides durable key-value storage via
`memory.put`, `memory.get`, `memory.list`, `memory.delete`, `memory.prune`.
Memory is backed by SQLite and configured via `AINL_MEMORY_DB`.

In orchestrated environments:

- memory is **recommended for stateful workflows** — any workflow that needs
  to persist facts, session context, or checkpoints across runs should include
  the `memory` adapter in its allowlist,
- memory is **optional for stateless workflows** — omit the `memory` adapter
  from the allowlist if the workflow is purely compute-and-respond,
- memory is **local** — each runtime instance has its own store,
- memory data can be exported/imported via JSON/JSONL bridges
  (`tooling/memory_bridge.py`).

Memory is classified as `extension_openclaw` by packaging origin. This reflects
where it was developed, not its importance. It is the primary durable state
mechanism across all deployment environments.
See also `docs/architecture/STATE_DISCIPLINE.md`.

See: `docs/adapters/MEMORY_CONTRACT.md`

### 7.2 Agent coordination

The AINL agent adapter provides a local, file-backed mailbox for inter-agent
coordination via `agent.send_task` and `agent.read_result`. Envelopes follow
the `AgentTaskRequest`/`AgentTaskResult` contract.

In orchestrated environments:

- coordination is **optional** — omit the `agent` adapter if not needed,
- coordination is **local** — file-backed under `AINL_AGENT_ROOT`,
- the orchestrator is responsible for consuming task files and producing
  result files,
- envelope policy fields (`approval_required`, `budget_limit`, etc.) are
  **advisory only** — AINL does not enforce them.

Coordination is classified as `extension_openclaw` and `noncanonical`.

See: `docs/advanced/AGENT_COORDINATION_CONTRACT.md`

---

## 8. Integration checklist

For orchestrators integrating with the AINL runner service:

- [ ] Query `GET /capabilities` to discover available adapters and runtime
  version
- [ ] Choose a submission mode: source code (`code`) or pre-compiled IR (`ir`)
- [ ] Choose an adapter allowlist profile
  (see `docs/operations/SANDBOX_EXECUTION_PROFILE.md`)
- [ ] Set runtime limits appropriate for your workload
- [ ] If policy enforcement is needed, include a `policy` object in `/run`
  requests
- [ ] Set container-level resource constraints (CPU, memory, timeout)
- [ ] Wire `GET /health` and `GET /ready` to your orchestrator's probe system
- [ ] Pipe runner stdout to your log aggregation system
- [ ] If using memory or coordination, configure `AINL_MEMORY_DB` and/or
  `AINL_AGENT_ROOT` to container-local paths
- [ ] Review `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` for the trust model

---

## 9. MCP server for AI coding agents

AINL includes an MCP (Model Context Protocol) server that exposes workflow
compilation, validation, execution, capability discovery, and security
introspection as MCP tools.  Any MCP-compatible host — Gemini CLI, Claude
Code, Codex Agents SDK, or a custom agent platform — can discover and call
AINL without custom integration code.

### Quick start

**Requirements:**

- Python 3.10+
- AINL installed with the MCP extra

```bash
pip install -e ".[mcp]"

# Start the stdio-based MCP server (no HTTP transport)
ainl-mcp
```

From an MCP-compatible host (for example, Gemini CLI, Claude Code, or another
MCP tool), configure a stdio transport pointing at the `ainl-mcp` command. The
host can then call the tools below.

### Exposed MCP tools

| Tool | Side effects | Description |
|------|-------------|-------------|
| `ainl_validate` | None | Check AINL source for syntax/semantic validity |
| `ainl_compile` | None | Compile AINL source to canonical graph IR |
| `ainl_capabilities` | None | Discover available adapters, verbs, and privilege tiers |
| `ainl_security_report` | None | Generate a per-label privilege/security map |
| `ainl_run` | Adapter calls (restricted) | Compile, policy-validate, and execute a workflow |

### Exposed MCP resources

| URI | Description |
|-----|-------------|
| `ainl://adapter-manifest` | Full adapter metadata (verbs, tiers, effects, privileges) |
| `ainl://security-profiles` | Named security profiles for deployment scenarios |

### Default security posture

`ainl_run` is restricted by default to the `core` adapter only, with
conservative resource limits and forbidden privilege tiers (`local_state`,
`network`, `operator_sensitive`). Callers can add further restrictions via
the `policy` parameter but cannot widen beyond the server defaults; they also
cannot enable raw adapter execution, advanced coordination, or memory mutation
tools over MCP v1.

### Minimal end-to-end example

The following sequence illustrates a minimal MCP interaction flow from a host
perspective:

1. **Validate** AINL source:

   ```json
   {
     "tool": "ainl_validate",
     "params": {
       "code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x"
     }
   }
   ```

2. **Compile** to canonical IR:

   ```json
   {
     "tool": "ainl_compile",
     "params": {
       "code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x"
     }
   }
   ```

3. **Run** under the safe-default profile:

   ```json
   {
     "tool": "ainl_run",
     "params": {
       "code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x",
       "strict": true
     }
   }
   ```

The host is responsible for wiring these calls into its own UI, prompts, and
policy layers; AINL’s MCP server provides only a thin, stdio-based workflow
surface with safe defaults.

### Source

`scripts/ainl_mcp_server.py`

### MCP exposure scoping

Operators can control which tools and resources the MCP server registers
at startup. This affects what MCP hosts can discover and call.

**Environment variables:**

| Variable | Effect |
|----------|--------|
| `AINL_MCP_EXPOSURE_PROFILE` | Named profile from `tooling/mcp_exposure_profiles.json` |
| `AINL_MCP_TOOLS` | Comma-separated inclusion list of tool names |
| `AINL_MCP_TOOLS_EXCLUDE` | Comma-separated exclusion list of tool names |
| `AINL_MCP_RESOURCES` | Comma-separated inclusion list of resource URIs |
| `AINL_MCP_RESOURCES_EXCLUDE` | Comma-separated exclusion list of resource URIs |

Resolution order: profile first, then env-var inclusion narrows further,
then exclusion subtracts from the result. If nothing is set, all tools and
resources are exposed.

**Named exposure profiles:**

| Profile | Tools | Resources |
|---------|-------|-----------|
| `validate_only` | `ainl_validate`, `ainl_compile` | none |
| `inspect_only` | validate + `ainl_capabilities` + `ainl_security_report` | all |
| `safe_workflow` | all 5 tools | all |
| `full` | all 5 tools | all |

Example:

```bash
AINL_MCP_EXPOSURE_PROFILE=validate_only ainl-mcp
```

**Context and governance benefits of scoped exposure:**

MCP hosts typically inject tool descriptions into the model's context
window so the model can decide which tools to call. Exposing fewer tools
reduces the tool-description overhead in the host's context, which can
improve model focus and reduce unnecessary tool-selection reasoning.
Narrower exposure also simplifies governance: operators and gateways have
fewer tools to audit, restrict, and monitor.

For example, a `validate_only` deployment exposes 2 tools instead of 5,
eliminating execution-related tool descriptions entirely. This is useful
when the host only needs AINL for syntax checking and IR inspection, not
workflow execution.

**Exposure scoping vs execution authorization:**

| Layer | Controls | File / mechanism |
|-------|----------|------------------|
| **MCP exposure profile** | Which tools/resources the host can discover | `tooling/mcp_exposure_profiles.json`, env vars |
| **Security profile / capability grant** | Which adapters, privilege tiers, limits are allowed at runtime | `tooling/security_profiles.json`, `AINL_MCP_PROFILE` |
| **Policy validation** | Which IR patterns are rejected before execution | `forbidden_adapters`, `forbidden_privilege_tiers`, etc. |

Exposure scoping is **additive to** security. Hiding `ainl_run` from the
host surface prevents discovery; the capability grant and policy still
enforce restrictions even when `ainl_run` is exposed.

### Deploying behind a gateway or proxy

AINL's MCP server is a **tool provider**, not a full MCP gateway. In
enterprise or multi-service deployments, a gateway/proxy/manager typically
sits in front of one or more MCP tool servers to provide:

- centralized authentication and authorization
- cross-server tool aggregation and routing
- DLP/PII governance
- audit aggregation across multiple tool providers
- per-user or per-team tool visibility

AINL provides what a gateway expects from a well-behaved tool provider:

| Concern | AINL provides | Gateway provides |
|---------|--------------|-----------------|
| Workflow compilation/execution | Yes | No |
| Tool/resource scoping | Yes (exposure profiles) | Yes (cross-server) |
| Capability grants and limits | Yes (restrictive-only) | Passes through |
| Structured audit events | Yes (JSON log events) | Aggregates across servers |
| Authentication / SSO / OAuth | **No** | Yes |
| DLP / PII scanning | **No** | Yes |
| Multi-tenant user management | **No** | Yes |
| Cross-server tool routing | **No** | Yes |

**Example deployment:**

```
┌──────────────────────────┐
│  MCP Gateway / Proxy     │ ← auth, governance, routing
│  (enterprise-managed)    │
├──────────────────────────┤
│         │                │
│  ┌──────▼──────┐  ┌─────▼─────┐
│  │ AINL MCP    │  │ Other MCP │
│  │ (tool       │  │ servers   │
│  │  provider)  │  │           │
│  └─────────────┘  └───────────┘
```

In this model:

1. Gateway authenticates the caller and enforces per-user/team policies.
2. Gateway routes MCP tool calls to the appropriate backend server.
3. AINL MCP server sees a pre-authorized request, applies its own
   exposure scoping, security profile, capability grant, and limits.
4. AINL emits structured audit log events; the gateway aggregates them.

To prepare AINL for gateway deployment:

```bash
# Restrict MCP surface to read-only inspection
AINL_MCP_EXPOSURE_PROFILE=inspect_only \
  AINL_MCP_PROFILE=local_minimal \
  ainl-mcp
```

### Relationship to the runner service and architecture

- The MCP server is a **peer** to the HTTP runner service
  (`scripts/runtime_runner_service.py`), not a replacement. Both reuse the same
  compiler, runtime engine, adapter metadata, policy validator, and
  security-report tooling.
- The runner service remains the primary **deployable product surface** for
  HTTP-based orchestrators (`/run`, `/enqueue`, `/result/{id}`, `/capabilities`,
  `/health`, `/ready`, `/metrics`).
- The MCP server exists to make AINL **workflow-level capabilities available to
  MCP-compatible AI coding agents** (Gemini CLI, Claude Code, Codex-style agent
  SDKs, generic MCP hosts) via stdio transport.
- v1 MCP intentionally **does not**:
  - expose raw adapter execution
  - expose advanced coordination tools
  - expose memory mutation tools
  - provide HTTP/SSE transport
  - act as an MCP gateway, auth plane, or control plane

---

## 10. Capability grant model

The runner service and MCP server use a **capability grant** to constrain
execution.  Grants are **restrictive-only**: merging a server grant with a
caller request always produces a result that is at least as restricted as
either input.

### Server grant from environment

Set `AINL_SECURITY_PROFILE` (runner) or `AINL_MCP_PROFILE` (MCP) to load
a named profile from `tooling/security_profiles.json` as the server grant:

```bash
AINL_SECURITY_PROFILE=sandbox_compute_and_store uvicorn scripts.runtime_runner_service:app
```

Available profiles: `local_minimal`, `sandbox_compute_and_store`,
`sandbox_network_restricted`, `operator_full`.

### Caller restrictions

Callers can pass `policy`, `limits`, and `allowed_adapters` in `/run`
requests. These are merged restrictively on top of the server grant —
callers can tighten but never widen beyond the server baseline.

### Structured audit logging

Every `/run` request emits structured JSON events:

- `run_start` — timestamp, trace ID, effective limits, policy presence
- `adapter_call` — per-call timestamp, status, duration, result hash (no raw payloads)
- `run_complete` / `run_failed` — final outcome

See [Audit Logging](AUDIT_LOGGING.md) for the full event schema.

### Adapter metadata

Adapters expose `destructive`, `network_facing`, and `sandbox_safe`
booleans via `/capabilities` and the adapter manifest. Policy rules
can use `forbidden_destructive: true` to reject all destructive adapters.

See [Capability Grant Model](CAPABILITY_GRANT_MODEL.md) for full details.

---

## 11. Relationship to other docs

- **Sandbox adapter and limit profiles:**
  `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- **Containerized deployment patterns:**
  `docs/operations/RUNTIME_CONTAINER_GUIDE.md`
- **Trust model and safe use:**
  `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`
- **Agent coordination contract:**
  `docs/advanced/AGENT_COORDINATION_CONTRACT.md`
- **Memory contract:**
  `docs/adapters/MEMORY_CONTRACT.md`
- **Adapter registry:**
  `docs/reference/ADAPTER_REGISTRY.md`
- **Adapter manifest (machine-readable):**
  `tooling/adapter_manifest.json`
- **Capabilities schema (machine-readable):**
  `tooling/capabilities.json`
- **Capability grant model:**
  `docs/operations/CAPABILITY_GRANT_MODEL.md`
- **Audit logging:**
  `docs/operations/AUDIT_LOGGING.md`
- **Runner service source:**
  `scripts/runtime_runner_service.py`
