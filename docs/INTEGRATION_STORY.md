## AINL Integration Story

AINL is the **workflow execution layer** inside your agent stack. It compiles
structured programs into canonical graph IR and executes them through a
controlled runtime with explicit state, adapter boundaries, and operator
governance. It does not replace your platform, sandbox, or orchestrator — it
sits inside them and makes agent workflows reproducible, inspectable, and
controllable.

---

## What AINL solves

Agent builders and operators hit the same pain points as their systems grow.
AINL was designed to reduce these specific pains:

| Pain point | How AINL addresses it | Where to look |
|------------|----------------------|---------------|
| **Workflow sprawl** | Compact programs compile to canonical graph IR; one source of truth per workflow | `docs/AINL_SPEC.md`, `docs/AINL_CANONICAL_CORE.md` |
| **Prompt-loop chaos** | Explicit steps, branches, loops, and error handling replace implicit prompt chains | `SEMANTICS.md`, `docs/language/AINL_EXTENSIONS.md` |
| **Brittle tool orchestration** | Retry with fixed or exponential backoff, error handlers, adapter-level isolation | `SEMANTICS.md` (Retry), `runtime/engine.py` |
| **Messy state handling** | Four explicit state tiers: frame, cache, memory, coordination | `docs/architecture/STATE_DISCIPLINE.md` |
| **Poor reproducibility** | Deterministic graph execution, record/replay adapter calls, compile-once IR | `docs/architecture/GRAPH_INTROSPECTION.md`, runner `/run` with `record_calls`/`replay_log` |
| **Difficult operator control** | Adapter allowlists, resource limits, optional policy validation at the runner boundary | `docs/operations/SANDBOX_EXECUTION_PROFILE.md`, `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` |
| **Scattered memory conventions** | Unified memory contract with namespaces, record kinds, and export/import bridges | `docs/adapters/MEMORY_CONTRACT.md`, `docs/architecture/STATE_DISCIPLINE.md` |
| **Weak interoperability between bots/tools/workflows** | Agent coordination envelopes, queue adapter, capability discovery endpoint | `docs/advanced/AGENT_COORDINATION_CONTRACT.md`, runner `GET /capabilities` |

---

## How AINL fits inside your agent stack

```
┌──────────────────────────────────────────────────────────┐
│  Your platform / orchestrator                            │
│  (OpenClaw, NemoClaw, custom host)                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Container / sandbox                               │  │
│  │                                                    │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  AINL runtime (runner service)               │  │  │
│  │  │                                              │  │  │
│  │  │  • compiles source → graph IR                │  │  │
│  │  │  • executes graph deterministically          │  │  │
│  │  │  • enforces adapter allowlists               │  │  │
│  │  │  • validates policy before execution         │  │  │
│  │  │  • manages state through explicit tiers      │  │  │
│  │  │  • exposes /capabilities, /run, /health      │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Orchestrator responsibilities:                          │
│  • container isolation, network policy                   │
│  • secret injection, authentication, TLS                 │
│  • scheduling, routing, multi-tenant isolation           │
│  • approval workflows, budget enforcement                │
│  • log aggregation, monitoring                           │
└──────────────────────────────────────────────────────────┘
```

AINL provides the **workflow execution** layer. Everything else — isolation,
networking, secrets, scheduling, approval — is the platform's responsibility.

---

## What AINL provides vs what your platform provides

| Concern | AINL provides | Your platform provides |
|---------|--------------|----------------------|
| Workflow compilation | Compiler (source → IR) | Decides when/what to compile |
| Graph execution | RuntimeEngine | Decides when to invoke |
| Adapter gating | Allowlist via `AdapterRegistry` | Chooses which adapters to allow |
| Resource limits | `max_steps`, `max_depth`, `max_time_ms` | Container CPU/memory/timeout |
| Policy validation | Optional `policy` on `/run` | Defines the policy |
| Capability discovery | `GET /capabilities` | Queries and acts on capabilities |
| Durable state | Memory adapter, SQLite adapter | Manages database backups, migrations |
| Container isolation | No | Process, filesystem, network isolation |
| Secret management | No | Inject via env or sidecar |
| Auth/TLS | No | Reverse proxy, ingress, mTLS |
| Multi-tenant isolation | No | One instance per tenant or orchestrator-level |
| Coordination routing | Local file-backed mailbox only | Routing, scheduling, retries |

For the full responsibility table, see
`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`.

---

## Integration surface

### 1. Discover capabilities

```
GET /capabilities
```

Returns the runtime version, available adapters (with verbs, support tiers,
and effect defaults), and whether policy validation is supported. Use this to
decide what adapter allowlist and policy to apply.

### 2. Submit a workflow

```
POST /run
{
  "code": "S app api /api\nL1:\nR core.ADD 2 3 ->sum\nJ sum",
  "allowed_adapters": ["core"]
}
```

Submit AINL source (or pre-compiled IR) for execution. The runner compiles,
executes, and returns a structured response with the output, trace ID, and
timing.

### 3. Apply policy (optional)

```
POST /run
{
  "code": "...",
  "policy": {
    "forbidden_adapters": ["http", "agent"],
    "forbidden_effects": ["io-write"]
  }
}
```

If the compiled IR violates the policy, the runner responds with HTTP 403 and
a structured list of violations without executing. Policy is entirely optional;
omitting it preserves default behavior.

---

## State discipline

AINL manages state through explicit tiers, not prompt history:

| Tier | Durability | Adapter | Use case |
|------|-----------|---------|----------|
| Frame | Single run | (built-in) | Scratch variables, intermediate results |
| Cache | Runtime instance | `cache` | Cooldowns, throttle state |
| Memory | Persistent | `memory` | Session context, long-term facts, checkpoints |
| Coordination | Cross-workflow | `queue`, `agent` | Handoffs, inter-agent tasks |

Memory is the recommended durable state mechanism for any stateful workflow.

For the full state model, see `docs/architecture/STATE_DISCIPLINE.md`.

---

## What AINL does NOT do

- **Not a control plane.** AINL executes workflows; it does not schedule,
  route, or manage multiple instances.
- **Not a sandbox.** AINL does not provide container isolation, network policy,
  or process sandboxing.
- **Not an agent platform.** AINL is a workflow execution layer, not a
  full agent framework with built-in planning, tool discovery, or autonomy.
- **Not MCP or A2A.** AINL does not implement Model Context Protocol or
  Agent-to-Agent protocol. It can sit alongside or underneath systems that do.

---

## Getting started (for platform integrators)

1. **Query capabilities.** `GET /capabilities` returns what the runtime
   supports. Use this to configure your allowlist and policy.
2. **Submit a workflow.** `POST /run` with source or IR, adapter allowlist,
   and optional policy.
3. **Add policy if needed.** Include a `policy` object in `/run` to restrict
   adapters and effects before execution.

For deployment patterns, see `docs/operations/RUNTIME_CONTAINER_GUIDE.md`.
For sandbox profiles, see `docs/operations/SANDBOX_EXECUTION_PROFILE.md`.
For the full external orchestrator guide, see
`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`.

---

## Why graph-native beats prompt loops

For a detailed comparison of graph-native agents vs prompt-loop agents — with
production evidence from real deployments — see
`docs/case_studies/graph_agents_vs_prompt_agents.md`.

For a cost analysis of compile-once vs invoke-every-run architectures, see
`docs/case_studies/HOW_AINL_SAVES_MONEY.md`.

---

## Positioning

AINL is **architecturally suited** to sit inside sandboxed, operator-controlled
agent environments such as OpenClaw, NemoClaw, and custom agent hosts. It
reduces workflow sprawl, prompt-loop chaos, brittle orchestration, messy state,
and poor reproducibility by providing a structured, graph-canonical execution
layer with explicit state discipline and operator governance.

AINL does not claim "compatible with" any specific platform. It claims to be
**designed to fit inside** the kinds of environments those platforms provide.

---

## Further reading

- Case study — graph-native vs prompt-loop agents: `docs/case_studies/graph_agents_vs_prompt_agents.md`
- Case study — runtime cost advantage: `docs/case_studies/HOW_AINL_SAVES_MONEY.md`
- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- OpenClaw example workflows: `examples/openclaw/`
- Workflow patterns for small models: `docs/PATTERNS.md`
- Competitive landscape: `README.md` (Competitive Landscape section)
