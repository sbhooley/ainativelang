# Capability Grant Model

The capability grant is AINL's **restrictive-only** host handshake mechanism.
It constrains what an execution surface (runner service, MCP server) is
allowed to do for a given run.

> This is runtime/host-level tooling. It does not change AINL language
> semantics, IR format, or per-node capabilities.

Related additive metadata: compiled IR may include `execution_requirements` (for example `avm_policy_fragment`, isolation/resource hints) to simplify AVM/general sandbox integration. This metadata is advisory and does not alter grant merge semantics.

## How it fits

The grant model ties together several related concepts:

| Concept | Role |
|---------|------|
| **Security profile** | Named baseline bundle of restrictions/defaults (e.g. `local_minimal`). Stored in `tooling/security_profiles.json`. |
| **Capability grant** | The effective restriction envelope for a run — derived by loading a security profile and merging with caller restrictions. |
| **Policy** | Execution-time IR checks extracted from the grant (`forbidden_adapters`, `forbidden_effects`, `forbidden_privilege_tiers`, etc.). |
| **Limits** | Resource ceilings (`max_steps`, `max_depth`, `max_adapter_calls`, etc.) extracted from the grant. |
| **Allowlist** | The final adapter surface permitted for a run — the intersection of server and caller `allowed_adapters`. |
| **Privilege tier** | Adapter risk classification metadata (`pure`, `local_state`, `network`, `operator_sensitive`). Used by policy, security reports, and grants. |
| **Adapter metadata** | Discovery/classification fields per adapter (`destructive`, `network_facing`, `sandbox_safe`, privilege tier). Exposed via `/capabilities`. |
| **Audit logging** | Structured runtime records of adapter activity emitted during execution. See `AUDIT_LOGGING.md`. |

The layering is:
- **AINL** provides deterministic graph execution, adapter gating, policy validation hooks, and audit events.
- **Runtime/host** (runner, MCP server) loads grants, registers adapters, selects profiles, manages secrets.
- **OS/container** provides actual hard process/network/filesystem isolation.

## Grant schema

A grant is a JSON-compatible dict with these fields:

| Field | Type | Merge rule | Description |
|---|---|---|---|
| `allowed_adapters` | `list[str] \| null` | intersection | Adapter allowlist; `null` = no restriction |
| `forbidden_adapters` | `list[str]` | union | Adapter blocklist |
| `forbidden_effects` | `list[str]` | union | Forbidden effect names |
| `forbidden_effect_tiers` | `list[str]` | union | Forbidden effect tiers |
| `forbidden_privilege_tiers` | `list[str]` | union | Forbidden privilege tiers |
| `limits` | `dict[str, int]` | per-key min | Runtime execution limits |
| `adapter_constraints` | `dict[str, dict]` | per-adapter restrictive merge | Per-adapter host/path/table restrictions |

## Restrictive-only merge

When two grants are merged (e.g. server grant + caller request), the result
is always **at least as restricted** as either input:

- **`allowed_adapters`**: intersection (narrows the allowlist)
- **`forbidden_*` fields**: union (widens the blocklist)
- **`limits`**: per-key minimum (more restrictive wins)
- **`adapter_constraints`**: per-adapter, per-field intersection for lists,
  min for numbers, AND for booleans

This guarantees that callers can add restrictions but never widen beyond
what the server allows.

## Server grant

Each execution surface loads a server-level grant at startup:

- **Runner service**: defaults to a permissive adapter cap (`allowed_adapters: null`)
  with conservative limits (`max_steps: 2000`, `max_depth: 20`, etc.).
  An operator can set `AINL_SECURITY_PROFILE` to load a named profile
  as the server grant.
- **MCP server**: defaults to a permissive adapter cap (`allowed_adapters: null`)
  with conservative limits (same floor as the runner). An operator can set
  `AINL_MCP_PROFILE` to load a named profile as the server grant, or enable
  `AINL_STRICT_MODE=1` to merge `consumer_secure_default` (or `AINL_STRICT_PROFILE`)
  with the resource floor.

## Composition flow

```
Security Profile (from env var)
    ↓
Server Grant (loaded at startup)
    ↓
Caller Request (from /run payload or MCP tool call)
    ↓
Restrictive Merge (merge_grants)
    ↓
Effective Grant → policy validator, adapter registry, runtime limits
```

## API

The grant model is implemented in `tooling/capability_grant.py`:

- `empty_grant()` — maximally permissive baseline
- `merge_grants(base, overlay)` — restrictive-only merge
- `grant_to_policy(grant)` — extract policy-validator-compatible subset
- `grant_to_limits(grant)` — extract limits dict
- `grant_to_allowed_adapters(grant, fallback)` — extract adapter allowlist
- `load_profile_as_grant(profile_name)` — load a named security profile as a grant

## Example

```python
from tooling.capability_grant import merge_grants

server = {
    "allowed_adapters": ["core", "http", "sqlite"],
    "forbidden_privilege_tiers": ["operator_sensitive"],
    "limits": {"max_steps": 2000},
    # ...
}

caller = {
    "allowed_adapters": ["core", "http"],
    "forbidden_adapters": ["sqlite"],
    "limits": {"max_steps": 500},
    # ...
}

effective = merge_grants(server, caller)
# allowed_adapters: ["core", "http"]  (intersection)
# forbidden_adapters: ["sqlite"]      (union)
# limits.max_steps: 500               (min)
```

## End-to-end operator walkthrough

This example shows the full security flow for a sandboxed deployment that
allows local computation and storage but no network access.

### 1. Choose a security profile and start the runner

```bash
AINL_SECURITY_PROFILE=sandbox_compute_and_store \
  uvicorn scripts.runtime_runner_service:app --host 0.0.0.0 --port 8770
```

The runner loads the `sandbox_compute_and_store` profile as the server
grant. This sets:

- `allowed_adapters`: `["core", "sqlite", "fs", "wasm", "memory", "cache"]`
- `forbidden_privilege_tiers`: `["network", "operator_sensitive"]`
- `limits`: `{"max_steps": 5000, "max_depth": 50, ...}`

### 2. Caller submits a workflow with additional restrictions

```json
POST /run
{
  "code": "S app api /api\nL1:\nR core.ADD 2 3 ->sum\nJ sum",
  "allowed_adapters": ["core"],
  "limits": {"max_steps": 500}
}
```

The runner **merges** the caller request with the server grant:

- `allowed_adapters` becomes `["core"]` (intersection of server and caller)
- `max_steps` becomes `500` (min of server's 5000 and caller's 500)
- `forbidden_privilege_tiers` stays `["network", "operator_sensitive"]` (union)

If the caller had tried `"allowed_adapters": ["core", "http"]`, the merge
would produce `["core"]` — `http` is not in the server grant, so it is
silently excluded. **Callers can tighten but never widen.**

### 3. Policy validation runs automatically

The effective grant is converted to a policy and checked against the
compiled IR. If the workflow uses `http.Get`, the policy rejects it
before execution with HTTP 403 and structured violations.

### 4. Audit log events are emitted

During execution the runner emits structured JSON log events:

```json
{"event": "run_start", "ts": "2026-03-09T14:22:01Z", "trace_id": "abc-123", "limits_summary": {"max_steps": 500}, "policy_present": true}
{"event": "adapter_call", "ts": "2026-03-09T14:22:01Z", "trace_id": "abc-123", "adapter": "core", "verb": "ADD", "status": "ok", "duration_ms": 0.4, "result_hash": "e3b0c4..."}
{"event": "run_complete", "trace_id": "abc-123"}
```

No raw results or secrets appear in the logs.

### 5. Capabilities can be inspected before submission

```bash
curl http://localhost:8770/capabilities
```

Returns each adapter's verbs, privilege tier, effect default, and metadata
flags (`destructive`, `network_facing`, `sandbox_safe`). Orchestrators
use this to build valid requests.

### What each layer provides

| Layer | Provides |
|-------|----------|
| **AINL** | Deterministic graph execution, adapter gating, policy validation, audit events |
| **Runtime/host** (runner) | Server grant from profile, restrictive merge, adapter registration, secrets |
| **OS/container** | Process isolation, filesystem mounts, network policy, resource limits |

## Related docs

- [Security Profiles](../../tooling/security_profiles.json) — named profiles
- [External Orchestration Guide](EXTERNAL_ORCHESTRATION_GUIDE.md) — integration patterns
- [Sandbox Execution Profile](SANDBOX_EXECUTION_PROFILE.md) — deployment postures
- [Audit Logging](AUDIT_LOGGING.md) — structured event schema
