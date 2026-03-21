## AINL Integration Story

AINL is the **workflow execution layer** inside your agent stack. It compiles
structured programs into canonical graph IR and executes them through a
controlled runtime with explicit state, adapter boundaries, and operator
governance. It does not replace your platform, sandbox, or orchestrator — it
sits inside them and makes agent workflows reproducible, inspectable, and
controllable.

**Public article (memory tiers, MCP hosts, bridge vs adapter):** [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents).

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
| **Difficult operator control** | Adapter allowlists, resource limits, optional policy validation at the runner boundary (including privilege tiers) | `docs/operations/SANDBOX_EXECUTION_PROFILE.md`, `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` |
| **Scattered memory conventions** | Unified memory contract with namespaces, record kinds, and export/import bridges | `docs/adapters/MEMORY_CONTRACT.md`, `docs/architecture/STATE_DISCIPLINE.md` |
| **Weak interoperability between bots/tools/workflows** | Agent coordination envelopes, queue adapter, capability + privilege discovery endpoint | `docs/advanced/AGENT_COORDINATION_CONTRACT.md`, runner `GET /capabilities` |

---

## How AINL fits inside your agent stack

```
┌──────────────────────────────────────────────────────────┐
│  Your platform / orchestrator                            │
│  (OpenClaw, NemoClaw, ZeroClaw, custom host)             │
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
effect defaults, and privilege tiers), and whether policy validation is supported.
Use this to decide what adapter allowlist, privilege tiers, and policy to apply.

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
    "forbidden_effects": ["io-write"],
    "forbidden_privilege_tiers": ["network", "operator_sensitive"]
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
- **Not an MCP host or A2A fabric.** AINL itself is not an agent host or
  Model Context Protocol provider in the sense of owning multi-agent session
  state. It now ships a **thin, stdio-only MCP server** (`ainl-mcp`) that
  exposes workflow-level tools and resources (validation, compilation,
  capabilities, security reports, safe-default `ainl_run`, and optional
  **ecosystem import** tools that fetch Clawflows / Agency-Agents Markdown and
  return deterministic `.ainl` source) to MCP-compatible
  hosts such as Gemini CLI, Claude Code, Codex-style agent SDKs, and other MCP
  hosts. This MCP surface is vendor-neutral, workflow-focused, and runs with
  safe-default restrictions (core-only adapters, conservative limits,
  `local_minimal`-style policy). Operators can further scope which tools and
  resources are exposed using MCP exposure profiles and env vars, especially
  when placing AINL behind an MCP gateway/manager. For desktop-bound agents
  (e.g. Cowork/Dispatch-style), start with **`inspect_only`** or
  **`validate_only`**; use **`safe_workflow`** only after operator review of
  grants, policies, and adapter exposure. It does *not* turn AINL into an
  agent platform, gateway, or control plane; it is an integration surface
  that sits alongside or underneath systems that do own sessions and policy.

For the **reverse direction** — workflows that call **out** to non-MCP HTTP
executors (webhooks, internal services, or a multi-backend gateway), see
[`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](integrations/EXTERNAL_EXECUTOR_BRIDGE.md).
That document is **MCP-first** for OpenClaw / NemoClaw / ZeroClaw: prefer `ainl-mcp` when the
host is MCP-capable; use the HTTP bridge pattern when workers are not exposed
as MCP. **OpenClaw** onboarding ( **`openclaw.json`** + **`ainl install-mcp --host openclaw`** ): **[`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**. **ZeroClaw** onboarding: **[`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)** · hub **[`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)**.

### ZeroClaw skill

**[ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw)** can consume AINL as a **ZeroClaw skill** checked into this repo:

```bash
zeroclaw skills install https://github.com/sbhooley/ainativelang/tree/main/skills/ainl
```

Run **`./install.sh`** or **`ainl install-mcp --host zeroclaw`** so **`ainl-mcp`** is registered under **`~/.zeroclaw/`** and **`ainl-run`** is on **`PATH`**. Narrative, chat examples, and ecosystem links: **[`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**. **Try:** *“Import the morning briefing using AINL.”*

### OpenClaw skill

**[OpenClaw](https://openclaw.ai/)** can consume AINL as a **skill** under **`~/.openclaw/skills`** or **`<workspace>/skills`** (copy **[`skills/openclaw/`](../skills/openclaw/)** or use **ClawHub** when available — not **`zeroclaw skills install`**).

Run **`./install.sh`** or **`ainl install-mcp --host openclaw`** so **`mcpServers.ainl`** is merged into **`~/.openclaw/openclaw.json`** and **`~/.openclaw/bin/ainl-run`** is available. Walkthrough: **[`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**. **Try:** *“Import the morning briefing using AINL.”*

### Import Clawflows & Agency-Agents via MCP

The MCP server (`scripts/ainl_mcp_server.py`) registers **`ainl_list_ecosystem`**,
**`ainl_import_clawflow`**, **`ainl_import_agency_agent`**, and
**`ainl_import_markdown`**. They call the same Markdown → AINL path as the CLI
importer (`tooling/markdown_importer.py`): **HTTPS fetch** when needed, then
return **`ainl` text** and **`meta`** in the tool result (no files written on
the server).

**Examples in `examples/ecosystem/`** in the repo are **kept fresh via weekly auto-sync** from upstream Clawflows and Agency-Agents (see **`.github/workflows/sync-ecosystem.yml`** and **`docs/ECOSYSTEM_OPENCLAW.md`**).

**Example chat prompts** (Claude Code, Cursor, Gemini CLI, ZeroClaw, or any MCP host):

- *“Run `ainl_list_ecosystem`, then import the **morning journal** Clawflow into AINL and validate the returned source with `ainl_validate`.”*
- *“Hey Claude, import the **morning briefing** Clawflow using AINL—use preset slug `morning-journal` or paste the raw `WORKFLOW.md` URL, then show me the graph.”*
- *“Import the Agency-Agents **MCP Builder** preset via `ainl_import_agency_agent` and summarize which labels the `.ainl` defines.”*

**Benefits:** upstream Markdown stays human-authored; AINL adds **compile-time
graph structure** (cron, sequential `Call` steps or agent gates, optional
OpenClaw-style `memory` / `queue` hooks; on **OpenClaw**, the same surface via **`skills/openclaw`** and **`ainl install-mcp --host openclaw`**; on **ZeroClaw**, the same importer and MCP tools via the **ZeroClaw skill** and **`ainl install-mcp --host zeroclaw`**) for **deterministic execution** at the
workflow layer—**compile-once, run-many** at the orchestration boundary. On tokenizer-aligned **viable subset** workloads (**tiktoken cl100k_base**), that structure pairs with roughly **~1.02×** leverage vs ad-hoc prompt-only flows; **legacy-inclusive** tables and **minimal_emit fallback stub** behavior are documented honestly in [`BENCHMARK.md`](../BENCHMARK.md) and [`benchmarks.md`](benchmarks.md).

**Governance:** these tools perform **outbound HTTPS**. They are enabled in
`safe_workflow` and `full` exposure profiles (`tooling/mcp_exposure_profiles.json`).
To hide them, set `AINL_MCP_TOOLS_EXCLUDE=ainl_import_clawflow,ainl_import_agency_agent,ainl_import_markdown` (or use a custom profile).

---

## Getting started (for platform integrators)

1. **Query capabilities.** `GET /capabilities` returns what the runtime
   supports, including adapter privilege tiers. Use this to configure your
   allowlist and policy.
2. **Submit a workflow.** `POST /run` with source or IR, adapter allowlist,
   and optional policy.
3. **Add policy if needed.** Include a `policy` object in `/run` to restrict
   adapters, effects, and privilege tiers before execution. For reusable
   defaults, see the named security profiles in `tooling/security_profiles.json`
   and the security report tool in `tooling/security_report.py`.

For deployment patterns, see `docs/operations/RUNTIME_CONTAINER_GUIDE.md`.
For sandbox profiles, see `docs/operations/SANDBOX_EXECUTION_PROFILE.md`.
For the full external orchestrator guide, see
`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`.
For AINL → external workers over HTTP, see
`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`.

---

## Claude Code / MCP agent role templates

The following MCP agent roles are intentionally narrow and map cleanly onto
AINL’s existing MCP tools and exposure profiles. They are written for Claude
Code and similar MCP-compatible hosts, but remain vendor-neutral.

- **AINL Validator Agent**
  - **Purpose**: validate AINL source only (syntax, graph IR).
  - **Recommended MCP exposure profile**: `validate_only`.
  - **Expected MCP tools**: `ainl_validate` (and optionally `ainl_compile`).

- **AINL Inspector / Security Reporter Agent**
  - **Purpose**: inspect capabilities, generate security reports, and explain
    runtime posture without executing workflows.
  - **Recommended MCP exposure profile**: `inspect_only`.
  - **Expected MCP tools**: `ainl_capabilities`, `ainl_security_report`,
    optionally `ainl_compile`.

- **AINL Safe Workflow Runner Agent**
  - **Purpose**: execute workflows only when explicitly intended and under
    safe-default restrictions.
  - **Recommended MCP exposure profile**: `safe_workflow`.
  - **Notes**: always pair with a reviewed security profile / capability grant,
    explicit policy, and limits. Operators must review adapter exposure and
    grants before enabling this role in desktop-bound or Cowork/Dispatch-style
    environments.

- **AINL Ecosystem Import Agent**
  - **Purpose**: discover curated Clawflows / Agency-Agents presets and fetch
    Markdown into deterministic `.ainl` source for validation or handoff to a
    runner—without shelling out to the CLI.
  - **Recommended MCP exposure profile**: `safe_workflow` or `full` (import
    tools are not in `validate_only` / `inspect_only`).
  - **Expected MCP tools**: `ainl_list_ecosystem`, `ainl_import_clawflow`,
    `ainl_import_agency_agent`, `ainl_import_markdown`, plus `ainl_validate` /
    `ainl_compile` as needed.

- **AINL Docs / Spec Researcher Agent**
  - **Purpose**: help reason about AINL docs, spec, and runtime contracts
    without executing workflows.
  - **Recommended MCP exposure profile**: `inspect_only` or a custom profile
    that exposes only read-only tools and resources.
  - **Expected surfaces**: AINL documentation, adapter manifest, and security
    profiles as read-only context; no `ainl_run` exposure.

In Claude Code, Claude Cowork / Dispatch, and Dispatch-style environments, AINL
fits best as a scoped MCP tool provider and deterministic workflow/runtime
layer beneath the host. Start with `validate_only` or `inspect_only` exposure
profiles, and only enable `safe_workflow` for explicitly approved runs after
operators have reviewed security profiles, capability grants, policies, limits,
and adapter exposure.

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
agent environments such as OpenClaw, NemoClaw, ZeroClaw, and custom agent hosts. It
reduces workflow sprawl, prompt-loop chaos, brittle orchestration, messy state,
and poor reproducibility by providing a structured, graph-canonical execution
layer with explicit state discipline and operator governance.

AINL does not claim "compatible with" any specific platform. It claims to be
**designed to fit inside** the kinds of environments those platforms provide.

---

## Further reading

- External executor bridge (HTTP; MCP-first): [`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](integrations/EXTERNAL_EXECUTOR_BRIDGE.md)
- Case study — graph-native vs prompt-loop agents: `docs/case_studies/graph_agents_vs_prompt_agents.md`
- Case study — runtime cost advantage: `docs/case_studies/HOW_AINL_SAVES_MONEY.md`
- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- OpenClaw skill + bootstrap: `docs/OPENCLAW_INTEGRATION.md`
- ZeroClaw skill + bootstrap: `docs/ZEROCLAW_INTEGRATION.md`
- OpenClaw example workflows: `examples/openclaw/`
- Workflow patterns for small models: `docs/PATTERNS.md`
- Competitive landscape: `README.md` (Competitive Landscape section)
