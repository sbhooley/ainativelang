## Sandbox Execution Profile

**Status:** Design/docs only. This document does not change compiler or runtime
semantics. It describes how to configure and deploy AINL inside sandboxed or
operator-controlled execution environments.

---

## 1. Purpose

This document provides prescriptive guidance for deploying AINL workflows inside
**sandboxed, containerized, or operator-controlled** execution environments such
as container orchestrators, restricted agent hosts, or managed runtime
platforms.

It answers:

- what AINL assumes about its execution environment,
- what AINL enforces vs what the sandbox/orchestrator must enforce,
- recommended adapter and limit profiles for different restriction levels,
- environment variable reference for sandbox configuration.

This guidance is **framework-agnostic**. It applies equally to any container
orchestrator, sandbox controller, or managed agent platform.

---

## 2. AINL's execution model in sandboxed environments

AINL is designed as a **workflow execution layer**, not a sandbox or security
layer. In a sandboxed deployment:

- The **sandbox/orchestrator** controls what resources are available (filesystem,
  network, process limits, available adapters).
- The **AINL runtime** executes deterministic graph workflows within those
  constraints, using only the adapters and resources made available to it.
- The **policy validator** (`tooling/policy_validator.py`) can serve as a
  pre-execution gate to reject IR that uses forbidden adapters or effects.

AINL does **not** provide:

- container isolation or process sandboxing,
- network policy enforcement,
- filesystem access control beyond adapter-level path containment,
- authentication, encryption, or multi-tenant isolation,
- automatic policy enforcement on coordination envelopes.

These are the responsibility of the hosting environment.

For the full trust model, see
`docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`.

---

## 3. Adapter allowlist profiles

The AINL runtime uses an explicit adapter allowlist via `AdapterRegistry`. Only
adapters in the allowlist can be called; all others raise `AdapterError`. This
is the primary capability gating mechanism.

Each adapter also has a **privilege tier** in metadata (e.g. `pure`,
`local_state`, `network`, `operator_sensitive`). These tiers do **not** change
runtime semantics; they exist to support policy validators and security reports
when deciding which adapters are appropriate for a given sandbox profile.

The following profiles are recommended starting points. Operators should adjust
based on their environment's requirements.

Named profile suggestions are also captured in `tooling/security_profiles.json`
for use in CI or external policy tooling. That JSON is intentionally small and
does not introduce a new policy language; it simply packages adapter
allowlists, privilege tiers, and runtime limit suggestions under a few
human-readable profile names.

Operators can load a named profile as the server-level **capability grant**
by setting `AINL_SECURITY_PROFILE` (runner) or `AINL_MCP_PROFILE` (MCP
server) at startup. The grant constrains what the execution surface is
allowed to do; callers can tighten restrictions per-request but never widen
beyond the grant. See `docs/operations/CAPABILITY_GRANT_MODEL.md`.

### 3.1 Minimal sandbox profile

Use when: the sandbox should only allow pure computation and deterministic
workflows with no external I/O.

```
Allowed adapters: core
```

- `core` — arithmetic, string, JSON, time operations (all `pure` effect)

Blocked: all I/O adapters (`http`, `sqlite`, `fs`, `tools`, `wasm`, `memory`,
`agent`, `svc`, `extras`, `tiktok`, `queue`, `cache`, `txn`, `auth`, `db`,
`email`, `calendar`, `social`)

This profile is suitable for:

- validating workflow logic without side effects,
- dry-run or simulation modes,
- environments where no external I/O is permitted.

### 3.2 Compute-and-store sandbox profile

Use when: the sandbox allows local computation and local storage but no
outbound network access.

```
Allowed adapters: core, sqlite, fs, wasm, memory, cache
```

- `core` — pure computation
- `sqlite` — local database (configure `allow_tables`, `allow_write`)
- `fs` — sandboxed filesystem (configure `sandbox_root`, `allow_extensions`)
- `wasm` — sandboxed WebAssembly modules (configure `module_allowlist`)
- `memory` — local memory store (configure `AINL_MEMORY_DB`); recommended for
  any workflow that needs durable state across runs
- `cache` — local cache

Blocked: all network-facing adapters (`http`, `agent`, `svc`, `extras`,
`tiktok`, `email`, `calendar`, `social`, `queue`, `tools`, `db`)

This profile is suitable for:

- offline or air-gapped environments,
- restricted containers with local storage only,
- environments where outbound network is blocked at the container level.

### 3.3 Network-restricted sandbox profile

Use when: the sandbox allows limited, controlled outbound network access with
explicit host allowlisting.

```
Allowed adapters: core, sqlite, fs, wasm, memory, cache, http, tools, queue
```

Additionally configure:

- `http` — set `allow_hosts` to a specific list (e.g. `["api.internal.example.com"]`)
- `tools` — set `allow_tools` to a specific list
- `fs` — set `sandbox_root` to a dedicated path

Blocked: extension/operator-only adapters (`agent`, `svc`, `extras`, `tiktok`,
`email`, `calendar`, `social`)

This profile is suitable for:

- containers with controlled egress rules,
- environments where network access is limited to known internal services,
- operator-controlled runtimes that need workflow I/O but not coordination.

### 3.4 Operator-controlled full profile

Use when: an operator has reviewed the workflow and explicitly enables all
needed adapters, including extension/coordination adapters.

```
Allowed adapters: operator's choice (any combination)
```

This profile is suitable for:

- trusted operator-managed environments,
- OpenClaw or similar platform deployments,
- environments where the orchestrator provides its own policy layer.

When using extension adapters (`agent`, `svc`, `extras`, `memory`, `tiktok`),
the operator accepts responsibility for the trust/safety considerations
documented in `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`.

---

## 4. Runtime limit profiles

The AINL runtime enforces resource limits via the `limits` parameter on
`RuntimeEngine`. These limits are independent of container-level resource
constraints and provide defense-in-depth.

### 4.1 Recommended limits for sandboxed execution

| Limit | Conservative | Standard | Permissive |
|-------|-------------|----------|------------|
| `max_steps` | 500 | 5,000 | 50,000 |
| `max_depth` | 10 | 50 | 200 |
| `max_adapter_calls` | 50 | 500 | 5,000 |
| `max_time_ms` | 5,000 | 30,000 | 300,000 |
| `max_frame_bytes` | 65,536 | 1,048,576 | 10,485,760 |
| `max_loop_iters` | 100 | 1,000 | 10,000 |

Choose based on your environment:

- **Conservative**: short-lived validation runs, untrusted workflows, CI checks
- **Standard**: typical production workflows, monitored containers
- **Permissive**: long-running operator-managed workflows with known resource needs

Container-level resource limits (CPU, memory, wall-clock timeout) should also
be set by the orchestrator as an outer boundary.

### 4.2 Limit configuration via CLI

```bash
ainl run program.ainl \
  --max-steps 5000 \
  --max-depth 50 \
  --max-adapter-calls 500 \
  --max-time-ms 30000 \
  --max-frame-bytes 1048576 \
  --max-loop-iters 1000
```

### 4.3 Limit configuration via runner service

Limits can be passed in the `/run` request body as a `limits` object:

```json
{
  "code": "...",
  "limits": {
    "max_steps": 5000,
    "max_depth": 50,
    "max_adapter_calls": 500,
    "max_time_ms": 30000,
    "max_frame_bytes": 1048576,
    "max_loop_iters": 1000
  }
}
```

---

## 5. Environment variable reference

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `AINL_AGENT_ROOT` | Sandbox root for agent coordination files | `/tmp/ainl_agents` | Must not be `/`; paths are contained under this root |
| `AINL_MEMORY_DB` | Path to SQLite memory store | `/tmp/ainl_memory.sqlite3` | Use a container-local path; ephemeral storage is acceptable |
| `AINL_SUMMARY_ROOT` | Root for `extras.metrics` output | (adapter-specific) | Restrict to a dedicated directory |

In sandboxed environments:

- Point these variables at **container-local, dedicated directories**.
- Do not set `AINL_AGENT_ROOT` to `/`, `$HOME`, or shared mounts.
- If the sandbox does not need agent coordination, do not enable the `agent`
  adapter and the `AINL_AGENT_ROOT` path is irrelevant.
- If the sandbox does not need persistent memory, use an ephemeral path for
  `AINL_MEMORY_DB` or do not enable the `memory` adapter.

---

## 6. What AINL enforces vs what the sandbox must enforce

| Concern | AINL enforces | Sandbox/orchestrator must enforce |
|---------|--------------|----------------------------------|
| Adapter capability gating | **Yes** — `AdapterRegistry` allowlist raises `AdapterError` for blocked adapters | Choose which adapters to register and allow |
| Runtime resource limits | **Yes** — `max_steps`, `max_depth`, `max_time_ms`, etc. | Set container-level CPU/memory/timeout limits as an outer boundary |
| Filesystem path containment | **Partially** — `SandboxedFileSystemAdapter` enforces `sandbox_root`, rejects path traversal | Restrict filesystem mounts and permissions at the container level |
| HTTP host restriction | **Partially** — `SimpleHttpAdapter` supports `allow_hosts` | Enforce network policy at the container/network level |
| SQLite table restriction | **Partially** — `SimpleSqliteAdapter` supports `allow_tables`, `allow_write` | Restrict database file access at the container level |
| WASM module restriction | **Partially** — `WasmAdapter` supports module allowlist | Restrict available WASM modules in the container |
| Agent sandbox root | **Partially** — `AgentAdapter` rejects `/` as root, enforces path containment | Choose a safe root path; restrict filesystem access |
| Policy on IR (forbidden adapters/effects) | **Available** — `tooling/policy_validator.py` can gate IR before execution | Invoke the policy validator as a pre-execution step |
| Network egress control | **No** | Enforce via container network policy |
| Process isolation | **No** | Enforce via container/OS isolation |
| Authentication/encryption | **No** | Enforce via container/orchestrator security |
| Multi-tenant isolation | **No** | Enforce via container/orchestrator boundaries |
| Coordination envelope policy fields | **No** — advisory only | Enforce `approval_required`, `budget_limit`, etc. in your orchestrator |

---

## 7. Pre-execution policy gate

The policy validator (`tooling/policy_validator.py`) can check compiled IR
against a declarative policy **before** execution begins.

### 7.1 Policy shape

```json
{
  "forbidden_adapters": ["http", "fs", "agent"],
  "forbidden_effects": ["io-write"],
  "forbidden_effect_tiers": ["network"],
  "forbidden_privilege_tiers": ["network", "operator_sensitive"]
}
```

### 7.2 Usage as a pre-execution gate

```python
from compiler_v2 import AICodeCompiler
from tooling.policy_validator import validate_ir_against_policy

compiler = AICodeCompiler()
ir = compiler.compile(source_code)

policy = {"forbidden_adapters": ["http", "fs"]}
result = validate_ir_against_policy(ir, policy)

if not result["ok"]:
    # Reject execution; result["errors"] contains structured violations
    raise RuntimeError(f"Policy violation: {result['errors']}")

# Proceed with execution
```

### 7.3 Policy via the runner service `/run` endpoint

The runner service accepts an optional `policy` object in the `/run` request
body. When present, the IR is validated against the policy before execution.
If the policy check fails, the service returns HTTP 403 with structured
violation details and does not execute the workflow.

```json
{
  "code": "L1: R http.Get \"https://example.com\" ->out J out\n",
  "policy": {
    "forbidden_adapters": ["http", "fs"]
  }
}
```

On policy violation, the response is:

```json
{
  "ok": false,
  "trace_id": "...",
  "error": "policy_violation",
  "policy_errors": [
    {
      "code": "POLICY_ADAPTER_FORBIDDEN",
      "message": "Adapter 'http' is forbidden by policy",
      "data": {"label_id": "1", "node_id": "n1", "adapter": "http"}
    }
  ]
}
```

When `policy` is omitted, the endpoint behaves as before (no policy check).

### 7.4 CLI usage

```bash
python -m tooling.policy_validator --ir program_ir.json --policy sandbox_policy.json
```

---

## 8. Adapter safety reference

For quick reference, each adapter's sandbox-relevant characteristics:

| Adapter | Tier | Default effect | Sandbox notes |
|---------|------|---------------|---------------|
| `core` | core | `pure` | Safe in all profiles; no I/O |
| `db` | core | `io` | Database I/O; restrict via backend config |
| `http` | core | `io` | Network I/O; restrict via `allow_hosts` |
| `sqlite` | core | `io` | Local DB; restrict via `allow_tables`, `allow_write` |
| `fs` | core | `io` | Filesystem; restrict via `sandbox_root`, `allow_extensions` |
| `tools` | core | `io` | External tool calls; restrict via `allow_tools` |
| `wasm` | core | `pure` | Sandboxed WASM; restrict via module allowlist |
| `cache` | core | `io` | Local cache; generally safe |
| `queue` | core | `io` | Queue write; depends on queue backend |
| `txn` | core | `io` | Transaction control; depends on DB backend |
| `auth` | core | `io` | Auth validation; depends on auth backend |
| `memory` | extension | `io` | Local SQLite; restrict via `AINL_MEMORY_DB` path |
| `agent` | extension | `io` | File-backed coordination; restrict via `AINL_AGENT_ROOT` |
| `svc` | extension | `io` | Service health checks; OpenClaw-specific |
| `extras` | extension | `io` | Monitoring extras; filesystem/Docker/HTTP probes |
| `tiktok` | extension | `io` | TikTok monitoring; OpenClaw-specific |
| `email` | extension | `io` | Email provider; external I/O |
| `calendar` | extension | `io` | Calendar provider; external I/O |
| `social` | extension | `io` | Social provider; external I/O |

---

## 9. Integration with external orchestrators

AINL is designed to sit inside external orchestrators, not to replace them.

A typical integration pattern for sandboxed execution:

1. **Orchestrator compiles or receives AINL IR** — either by invoking the AINL
   compiler or by accepting pre-compiled IR as a portable JSON artifact.
2. **Orchestrator applies policy gate** — either by including a `policy` object
   in the `/run` request (the runner validates IR before execution and returns
   HTTP 403 on violations), or by invoking `validate_ir_against_policy()`
   directly as a pre-execution step.
3. **Orchestrator configures the runtime** — sets adapter allowlist, runtime
   limits, and environment variables appropriate for the sandbox.
4. **Orchestrator invokes execution** — either via the runner service (`/run`)
   or by instantiating `RuntimeEngine` directly with configured adapters.
5. **Orchestrator inspects results** — uses structured JSON output, traces,
   and health endpoints to monitor and audit execution.

The AINL runtime does not need to know which orchestrator is managing it. The
adapter allowlist, limits, and environment variables are the configuration
surface. The orchestrator can query `GET /capabilities` on the runner service
to discover available adapters, verbs, support tiers, and runtime version
before submitting workflows.

For coordination with external agents via `AgentTaskRequest`/`AgentTaskResult`
envelopes, see `docs/advanced/AGENT_COORDINATION_CONTRACT.md`.

---

## 10. Relationship to other docs

- **Capability grant model:** `docs/operations/CAPABILITY_GRANT_MODEL.md`
- **Structured audit logging:** `docs/operations/AUDIT_LOGGING.md`
- **External orchestration guide:** `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- **Runtime container guide:** `docs/operations/RUNTIME_CONTAINER_GUIDE.md`
- **Trust model and safe use:** `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`
- **Agent coordination:** `docs/advanced/AGENT_COORDINATION_CONTRACT.md`
- **Memory contract:** `docs/adapters/MEMORY_CONTRACT.md`
- **Adapter registry:** `docs/reference/ADAPTER_REGISTRY.md`
- **Capability registry:** `docs/reference/CAPABILITY_REGISTRY.md`
- **Adapter manifest (machine-readable):** `tooling/adapter_manifest.json`
- **Capabilities schema (machine-readable):** `tooling/capabilities.json`
- **Support matrix (machine-readable):** `tooling/support_matrix.json`
- **MCP server for MCP-compatible hosts:** `scripts/ainl_mcp_server.py`
  (documented in `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`, section **9**)
  exposes the same workflow/policy surfaces over Model Context Protocol. It is
  stdio-only, runs with safe-default restrictions (core-only adapters,
  conservative limits, `local_minimal`-style policy), and does *not* change
  the sandbox assumptions described in this document.
