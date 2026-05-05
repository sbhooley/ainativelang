# Agent guides — index

If you are an AI agent that just needs AINL **installed** into your host
stack, do **not** read these guides. Run the one-step install from the top
of [`../../AGENTS.md`](../../AGENTS.md) or [`../../README.md`](../../README.md):

```bash
pipx install 'ainativelang[mcp]' && ainl setup --auto
```

That command auto-detects every supported host (Claude Code, Cursor, Cline,
Codex CLI/Desktop, Claude Desktop, OpenClaw, Hermes, ArmaraOS, or any
generic MCP host) and registers AINL's MCP server with each. No further
reading is required.

The guides below are for agents that have already installed AINL and need
deeper context for specific operator workflows or debugging.

## Index

| Guide | Audience | What it covers |
|-------|----------|----------------|
| [`openclaw-quickstart.md`](openclaw-quickstart.md) | Agents authoring AINL workflows for OpenClaw | Zero-to-first-workflow path; required reading list before implementation work |
| [`openclaw-overview.md`](openclaw-overview.md) | Agents new to the OpenClaw integration | Conceptual overview of how AINL plugs into OpenClaw |
| [`openclaw-operator.md`](openclaw-operator.md) | OpenClaw operators tuning the integration | Day-to-day operator commands, status checks, doctor output reading |
| [`continuity.md`](continuity.md) | Agents in long-running sessions | Session-continuity patterns, handoff packets, agent-to-agent communication |

## Where to find install-time info

- One-step install: top of [`../../AGENTS.md`](../../AGENTS.md) and [`../../README.md`](../../README.md)
- Per-host details (advanced, manual paths): "Per-host details" section in [`../../README.md`](../../README.md)
- Machine-readable spec: [`../../.agent-install.json`](../../.agent-install.json)
- Design contract: [`../architecture/2026-05-05-agent-install-simplification.md`](../architecture/2026-05-05-agent-install-simplification.md)

## Migration notes

These four guides previously lived at top-level / `docs/` paths. They were
consolidated under `docs/agents/` so the repo presents one canonical place
for agent-specific operator content. Stubs at the original paths point
here, so external links continue to resolve through one extra hop.

| Old location | New location |
|--------------|--------------|
| `AI_AGENT_QUICKSTART_OPENCLAW.md` | `docs/agents/openclaw-quickstart.md` |
| `OPENCLAW_AI_AGENT.md` | `docs/agents/openclaw-overview.md` |
| `docs/AI_AGENT_CONTINUITY.md` | `docs/agents/continuity.md` |
| `docs/QUICKSTART_OPENCLAW.md` | `docs/agents/openclaw-operator.md` |
