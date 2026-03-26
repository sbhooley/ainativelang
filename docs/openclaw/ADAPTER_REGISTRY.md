# Adapter Registry Notes

The `ADAPTER_REGISTRY.json` is the machine-readable catalog of adapter capabilities.

**Important:** The `agent` adapter is deliberately minimal. It exposes only:
- `send_task`
- `read_result`

Verbs like `read_task` or `list_agents` are **not** supported and must not be used. See `AGENT_COORDINATION_CONTRACT.md` for the shared protocol boundary.
