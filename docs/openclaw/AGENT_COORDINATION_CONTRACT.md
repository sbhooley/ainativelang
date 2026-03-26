# Agent Coordination Contract (Cursor ↔ OpenClaw)

## Shared Protocol Surface

The coordination substrate between AI agents uses a local file-backed mailbox. The agreed verbs are:

- `agent.send_task(envelope)` → writes an `AgentTaskRequest` to `$AINL_AGENT_ROOT/tasks/openclaw_agent_tasks.jsonl` and returns the `task_id`.
- `agent.read_result(task_id)` → reads the `AgentTaskResult` from `$AINL_AGENT_ROOT/results/<task_id>.json`.

## Boundaries

- `read_task` and `list_agents` are **NOT** part of the shared protocol.
- No polling, routing, discovery, or swarm semantics are implied.
- Result creation and task consumption remain external orchestration responsibilities.

## Envelope Schemas

**AgentTaskRequest** (written by sender):
```json
{
  "task_id": "string",
  "requester_id": "string",
  "target_agent": "string",
  "task_type": "string",
  "description": "string",
  "input": {},
  "allowed_tools": ["string"],
  "approval_required": false,
  "callback": null,
  "metadata": {}
}
```

**AgentTaskResult** (written by receiver):
```json
{
  "schema_version": "0.1",
  "task_id": "string",
  "agent_id": "string",
  "status": "success|failure|partial|cancelled",
  "confidence": 0.0-1.0,
  "output": {},
  "needs_review": false,
  "error": {},
  "provenance_ref": "string"
}
```

## File Layout

- Tasks: `$AINL_AGENT_ROOT/tasks/openclaw_agent_tasks.jsonl` (JSON Lines, append-only)
- Results: `$AINL_AGENT_ROOT/results/<task_id>.json`

Defaults: `AINL_AGENT_ROOT` = `/tmp/ainl_agents`
