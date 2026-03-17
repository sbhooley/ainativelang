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
| `adapters` | Map of available adapter namespaces with verbs, tier, default effect, and lane |
| `adapters[name].support_tier` | `core` (canonical), `compatibility`, or `extension_openclaw` |
| `adapters[name].recommended_lane` | `canonical` or `noncanonical` |

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
    "forbidden_effect_tiers": ["network"]
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

## 9. Relationship to other docs

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
- **Runner service source:**
  `scripts/runtime_runner_service.py`
