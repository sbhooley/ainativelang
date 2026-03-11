## Agent Coordination Contract (draft, extension/OpenClaw lane)

**Status:** Design/spec only. This document defines **typed JSON envelopes** for
agent manifests, task requests, and task results. It does **not** change any
compiler/runtime semantics and is intended for extension/OpenClaw agent
orchestrators (e.g. OpenClaw, ClaudeBot, future local/remote agents).

The design is:

- **explicit** — no hidden delegation or recursion,
- **typed** — small, versioned JSON schemas,
- **bounded** — transport is queue/file‑backed by convention,
- **auditable** — envelopes carry provenance and artifact references,
- **policy‑aware** — trust/approval/budget fields are first‑class,
- **replayable** — results link back to AINL runs and traces.

Use this as the contract for inter‑agent coordination built **on top of** AINL,
not as a core language feature.

---

## 1. Agent capability manifest (`AgentManifest`)

Minimal JSON schema (conceptual, versioned via `schema_version`):

```json
{
  "schema_version": "1.0",

  "agent_id": "string",
  "name": "string",
  "version": "string",
  "description": "string",

  "role_types": [
    "advisor",
    "executor",
    "reviewer"
  ],

  "available_tools": [
    "http",
    "queue",
    "fs.read-only",
    "openclaw.notifications"
  ],

  "execution_mode": "advisory",

  "trust_domain": "internal",

  "requires_human_approval": {
    "default": false,
    "for_task_types": {
      "deploy": true,
      "high_risk_change": true
    }
  },

  "budget_class": "medium",
  "locality": "local",
  "max_context_size": 16384,

  "contact": {
    "queue": "agent_tasks",
    "inbox_file": "agents/openclaw.monitor/inbox.jsonl"
  },

  "policy_refs": [
    "policy://internal/agent-safety/v1"
  ],

  "provenance": {
    "owner": "OpenClaw monitors",
    "created_at": "2026-03-09T00:00:00Z",
    "source_repo": "https://github.com/sbhooley/ainativelang"
  }
}
```

### 1.1 Example: OpenClaw monitor agent manifest

```json
{
  "schema_version": "1.0",
  "agent_id": "openclaw.monitor",
  "name": "OpenClaw Infrastructure Monitor",
  "version": "1.0.0",
  "description": "Runs AINL-based infrastructure and SLA monitors and emits alerts.",

  "role_types": ["executor", "advisor"],
  "available_tools": [
    "http",
    "queue",
    "svc",
    "extras",
    "tiktok",
    "fs.read-only"
  ],
  "execution_mode": "hybrid",

  "trust_domain": "internal",
  "requires_human_approval": {
    "default": false,
    "for_task_types": {
      "prod_deploy": true,
      "high_risk_change": true
    }
  },
  "budget_class": "medium",
  "locality": "local",
  "max_context_size": 32768,

  "contact": {
    "queue": "openclaw_agent_tasks",
    "inbox_file": "agents/openclaw.monitor/inbox.jsonl"
  },

  "policy_refs": [
    "policy://internal/agent-safety/v1"
  ],

  "provenance": {
    "owner": "Steven Hooley / OpenClaw",
    "created_at": "2026-03-09T00:00:00Z",
    "source_repo": "https://github.com/sbhooley/ainativelang"
  }
}
```

This describes **what the agent can do** and **how to talk to it**, but does not
imply any automatic wiring in AINL.

---

## 2. Task request envelope (`AgentTaskRequest`)

Minimal JSON schema:

```json
{
  "schema_version": "1.0",

  "task_id": "string",
  "requester_id": "string",
  "target_agent": "string",
  "target_role": "string",

  "task_type": "string",
  "description": "string",

  "input": {
    "refs": [
      {
        "kind": "string",
        "uri": "string"
      }
    ],
    "payload": {}
  },

  "required_output_contract": {
    "format": "json",
    "schema_ref": "schema://ainl/agent-output/v1",
    "must_include_fields": ["status", "summary", "actions"]
  },

  "sensitivity": "internal",
  "deadline": "string|null",

  "budget_limit": {
    "tokens": 2000,
    "usd_cents": 500
  },

  "allowed_tools": [
    "http",
    "openclaw.notifications"
  ],

  "approval_required": "none",
  "human_approver": "string|null",

  "callback": {
    "queue": "agent_results",
    "file_append": "agents/openclaw.monitor/results.jsonl"
  },

  "policy_context": {
    "environment": "staging",
    "change_window": "2026-03-10T01:00:00Z/2026-03-10T02:00:00Z"
  },

  "metadata": {
    "ainl.graph_checksum": "string",
    "ainl.program_id": "string"
  }
}
```

### 2.1 Example: local queue/file-backed task handoff

Example request from a planner/dispatcher agent to `openclaw.monitor` asking it
to run a TikTok SLA check (using an AINL program like
`examples/autonomous_ops/tiktok_sla_monitor.lang`):

```json
{
  "schema_version": "1.0",
  "task_id": "task-2026-03-09-0001",
  "requester_id": "planner.agent",
  "target_agent": "openclaw.monitor",
  "target_role": "executor",

  "task_type": "execute_monitor",
  "description": "Run TikTok SLA monitor and report whether KPIs are within bounds.",

  "input": {
    "refs": [
      {
        "kind": "ainl_program",
        "uri": "file://examples/autonomous_ops/tiktok_sla_monitor.lang"
      }
    ],
    "payload": {
      "sla_hours": 24
    }
  },

  "required_output_contract": {
    "format": "json",
    "schema_ref": "schema://ainl/agent-output/v1",
    "must_include_fields": ["status", "summary", "actions"]
  },

  "sensitivity": "internal",
  "deadline": "2026-03-09T23:00:00Z",

  "budget_limit": {
    "tokens": 3000,
    "usd_cents": 300
  },

  "allowed_tools": [
    "http",
    "queue",
    "svc",
    "extras",
    "tiktok"
  ],

  "approval_required": "pre",
  "human_approver": "sre-oncall@example.com",

  "callback": {
    "queue": "agent_results",
    "file_append": "agents/openclaw.monitor/results.jsonl"
  },

  "policy_context": {
    "environment": "staging",
    "change_window": "2026-03-10T01:00:00Z/2026-03-10T02:00:00Z"
  },

  "metadata": {
    "ainl.graph_checksum": "sha256:...",
    "ainl.program_id": "tiktok_sla_monitor.v1"
  }
}
```

By convention, this envelope would be written to a queue or JSONL file that the
`openclaw.monitor` agent consumes; AINL itself does not interpret this schema.

---

## 3. Task result envelope (`AgentTaskResult`)

Minimal JSON schema:

```json
{
  "schema_version": "1.0",

  "task_id": "string",
  "agent_id": "string",

  "status": "string",
  "confidence": "number|null",

  "output": {
    "summary": "string",
    "actions": [
      {
        "kind": "string",
        "description": "string",
        "status": "pending|executed|skipped"
      }
    ]
  },

  "artifact_refs": [
    {
      "kind": "string",
      "uri": "string"
    }
  ],

  "cost_used": {
    "tokens": 0,
    "usd_cents": 0
  },

  "time_used": {
    "started_at": "string",
    "finished_at": "string",
    "wall_ms": 0
  },

  "needs_review": {
    "required": false,
    "reason": "string|null"
  },

  "error": {
    "kind": "string|null",
    "message": "string|null"
  },

  "provenance_ref": {
    "ainl_graph_checksum": "string",
    "ainl_program_id": "string",
    "runtime_version": "string",
    "recording_uri": "string"
  }
}
```

### 3.1 Example: result with status, review flag, and provenance

Example result after `openclaw.monitor` runs a TikTok SLA monitor and records
its execution using AINL’s record/replay tooling:

```json
{
  "schema_version": "1.0",
  "task_id": "task-2026-03-09-0001",
  "agent_id": "openclaw.monitor",

  "status": "ok",
  "confidence": 0.9,

  "output": {
    "summary": "TikTok SLA is within bounds: all KPIs within 24h window are green.",
    "actions": [
      {
        "kind": "notification",
        "description": "No remediation required; log daily SLA summary.",
        "status": "executed"
      }
    ]
  },

  "artifact_refs": [
    {
      "kind": "run_summary",
      "uri": "file://runs/tiktok_sla_monitor/2026-03-09/summary.json"
    },
    {
      "kind": "run_trace",
      "uri": "file://runs/tiktok_sla_monitor/2026-03-09/trace.json"
    }
  ],

  "cost_used": {
    "tokens": 0,
    "usd_cents": 0
  },

  "time_used": {
    "started_at": "2026-03-09T20:00:00Z",
    "finished_at": "2026-03-09T20:00:05Z",
    "wall_ms": 5000
  },

  "needs_review": {
    "required": false,
    "reason": null
  },

  "error": {
    "kind": null,
    "message": null
  },

  "provenance_ref": {
    "ainl_graph_checksum": "sha256:...",
    "ainl_program_id": "tiktok_sla_monitor.v1",
    "runtime_version": "ainl-runtime-1.0.0",
    "recording_uri": "file://runs/tiktok_sla_monitor/2026-03-09/calls.json"
  }
}
```

This envelope is designed to be:

- **typed and bounded** — no freeform chat,
- **policy‑aware** — `needs_review`, `status`, and `error` are explicit,
- **replayable** — `provenance_ref` ties back to AINL runs and recordings.

---

## 4. Scope and non-goals (for this pass)

- These schemas are **non‑canonical** and **extension‑level**:
  - they are not part of the AINL language semantics,
  - they are intended for OpenClaw / orchestrators / external agents.
- AINL **does not**:
  - interpret these envelopes in the compiler or core runtime,
  - provide built‑in swarm/recursive agent semantics in this pass,
  - implicitly route tasks between agents.
- Future work (separate passes) may:
  - add extension adapters that read/write these envelopes via queues/files,
  - define policy engines and approval flows that consume `trust_domain`,
    `sensitivity`, `approval_required`, and `needs_review`,
  - extend locality/trust modeling to remote/federated agents.

### 4.1 AINL example using `agent.send_task`

For a concrete extension-level AINL example that builds a small
`AgentTaskRequest` envelope and appends it to a sandboxed JSONL file via the
`agent` adapter, see:

- `examples/openclaw/agent_send_task.lang`

That example:

- runs locally and uses `AINL_AGENT_ROOT` (default `/tmp/ainl_agents`) as the
  sandbox root,
- constructs an envelope with:
  - `task_id`, `requester_id`, `target_agent`, `target_role`,
  - `task_type`, `description`, `input.refs`, `input.payload`,
  - `allowed_tools`, `approval_required`, `callback.file_append`,
  - `metadata.ainl.program_id`,
- and calls:

```text
R agent send_task task "tasks/openclaw_agent_tasks.jsonl" ->result
```

The resulting JSONL file lives under `AINL_AGENT_ROOT` and can be consumed by an
external orchestrator that understands the `AgentTaskRequest` schema.

### 4.2 AINL example using `agent.read_result`

For a concrete extension-level AINL example that reads a single
`AgentTaskResult` envelope identified by `task_id` via the `agent` adapter,
see:

- `examples/openclaw/agent_read_result.lang`

That example:

- assumes a result file exists at
  `AINL_AGENT_ROOT/results/demo-openclaw-monitor-001.json`,
- and calls:

```text
R agent read_result "demo-openclaw-monitor-001" ->result
```

The result is a JSON object compatible with the `AgentTaskResult` schema and
can be inspected or returned by the AINL program. Creation and placement of the
result file remains the responsibility of an external orchestrator or human.

---

## 5. Local coordination loop walkthrough (extension/OpenClaw)

This section shows how the minimal local coordination loop fits together using
files under `AINL_AGENT_ROOT` (default: `/tmp/ainl_agents`).

### 5.1 Suggested file layout under `AINL_AGENT_ROOT`

By convention, you can use the following layout:

- `AINL_AGENT_ROOT/tasks/openclaw_agent_tasks.jsonl` — JSONL file of
  `AgentTaskRequest` envelopes written by `agent.send_task`.
- `AINL_AGENT_ROOT/results/demo-openclaw-monitor-001.json` — JSON file
  containing a single `AgentTaskResult` envelope for a specific task.

In this repository, an example `AgentTaskResult` file is provided at:

- `examples/openclaw/demo-openclaw-monitor-001.result.json`

You can copy or move that file under your own `AINL_AGENT_ROOT/results/`
directory when testing the local loop.

### 5.2 End-to-end local loop (manual steps)

1. **Configure sandbox root (optional)**:

   ```bash
   export AINL_AGENT_ROOT=/tmp/ainl_agents
   ```

   If not set, the adapter defaults to `/tmp/ainl_agents`.

2. **Send a task from AINL**:

   Run the extension example that enqueues a task:

   ```bash
   # inside the repo root
   ainl-validate examples/openclaw/agent_send_task.lang
   ainl run examples/openclaw/agent_send_task.lang --json
   ```

   After this, you should have:

   - `$AINL_AGENT_ROOT/tasks/openclaw_agent_tasks.jsonl` containing a line with
     a `task_id` of `demo-openclaw-monitor-001`.

3. **Place a result file (external/orchestrator step)**:

   An external orchestrator or a human operator is responsible for creating a
   compatible `AgentTaskResult` JSON file. For testing, you can seed one from
   the provided example:

   ```bash
   mkdir -p "$AINL_AGENT_ROOT/results"
   cp examples/openclaw/demo-openclaw-monitor-001.result.json \
      "$AINL_AGENT_ROOT/results/demo-openclaw-monitor-001.json"
   ```

4. **Read the result from AINL**:

   Run the extension example that reads the result:

   ```bash
   ainl-validate examples/openclaw/agent_read_result.lang
   ainl run examples/openclaw/agent_read_result.lang --json
   ```

   This will load the JSON object from
   `$AINL_AGENT_ROOT/results/demo-openclaw-monitor-001.json` (derived from the
   task id) and bind it to `result` within the program.

### 5.3 Out-of-scope for this local loop

The current design and examples intentionally **do not** provide:

- automatic task routing between agents,
- task/result polling or watching,
- queue-backed result transport,
- remote or federated agent communication,
- policy enforcement or approval workflows,
- recursive or swarm-style multi-agent behavior.

Those concerns are expected to be handled by higher-level orchestrators or
future, explicitly-scoped design passes.

---

## 6. Shared protocol boundary (Cursor ↔ OpenClaw)

For shared, local-only coordination between Cursor-side and OpenClaw-side
workflows, the **only** accepted adapter surface in this pass is:

- `agent.send_task`
- `agent.read_result`

Any additional verbs that might exist in specific OpenClaw environments
(`read_task`, `list_agents`, or similar) are **not** part of the shared
cross-tool protocol and MUST NOT be relied on by Cursor or other external
tools.

The contract boundary is:

- AINL/OpenClaw programs:
  - may **write** `AgentTaskRequest` envelopes using `agent.send_task`,
  - may **read** `AgentTaskResult` envelopes using `agent.read_result`.
- External orchestrators (including Cursor) are responsible for:
  - consuming task JSONL files under `AINL_AGENT_ROOT/tasks/`,
  - creating/placing result JSON files under `AINL_AGENT_ROOT/results/`,
  - handling any routing, discovery, polling, or policy decisions.

No swarm behavior, routing, discovery (`list_agents`), or task-reading helpers
(`read_task`) are part of the shared protocol at this time.

---

## 7. Real-world advisory example: token-cost review loop

As a small, practical use of the local mailbox protocol, the repository
includes a **token-cost advisory loop**:

- `examples/openclaw/token_cost_advice_request.lang` — assembles bounded
  token/cost usage facts and enqueues an `AgentTaskRequest` asking a
  Cursor-side advisor to review daily token cost and suggest safe model/usage
  optimizations.
- `examples/openclaw/token_cost_advice_read.lang` — reads a single
  `AgentTaskResult` for a known advisory `task_id` via `agent.read_result`.

The flow is:

1. **AINL/OpenClaw writes an advisory request**

   Run the request example:

   ```bash
   ainl-validate examples/openclaw/token_cost_advice_request.lang
   ainl run examples/openclaw/token_cost_advice_request.lang --json
   ```

   This appends an `AgentTaskRequest` with `task_id:
   "token-cost-advice-20260309"` to:

   - `$AINL_AGENT_ROOT/tasks/openclaw_agent_tasks.jsonl`

2. **Cursor/External agent writes the advisory result**

   A Cursor-side workflow reads the tasks JSONL file, computes advisory
   recommendations (e.g. which models to downrank or where to cap usage), and
   writes an `AgentTaskResult` JSON file to:

   - `$AINL_AGENT_ROOT/results/token-cost-advice-20260309.json`

   using the `AgentTaskResult` schema in this document.

3. **AINL/OpenClaw reads the advisory result**

   Run the result reader example:

   ```bash
   ainl-validate examples/openclaw/token_cost_advice_read.lang
   ainl run examples/openclaw/token_cost_advice_read.lang --json
   ```

   This loads the advisory `AgentTaskResult` for
   `task_id="token-cost-advice-20260309"` and binds it to `result` within the
   program.

This example remains:

- local-only and file-backed under `AINL_AGENT_ROOT`,
- advisory-only (no remediation or orchestration in AINL),
- externally orchestrated (Cursor or another agent is responsible for routing
  and writing the result),
- and fully aligned with the narrow shared protocol
  (`agent.send_task` / `agent.read_result`).

