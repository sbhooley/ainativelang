# Operations

Use this section for real deployment-style operational docs: monitors, playbooks, health envelopes, and recurring workflow patterns.

## Key docs

- [`OPENCLAW_AINL_GOLD_STANDARD.md`](OPENCLAW_AINL_GOLD_STANDARD.md) — **OpenClaw + AINL gold standard** (profiles, caps, cron, host behavior, verification); **`openclaw_ainl_gold_standard`**
- [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md) — **AINL v1.2.8 host briefing** (bridge probe, rolling hydrate, profiles, explicit OpenClaw responsibilities); **`openclaw_host_ainl_1_2_8`**
- [`AINL_PROFILES.md`](AINL_PROFILES.md) — **named env profiles** (`ainl profile list|show|emit-shell`), portable defaults for many installs
- [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) — separate DBs/paths per workspace or tenant
- [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) — OpenClaw reference bundle (links bootstrap + monitoring + profiles)
- [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) — long-term roles (agent vs AINL), host contract, default loop, agent checklist
- [`UNIFIED_MONITORING_GUIDE.md`](UNIFIED_MONITORING_GUIDE.md) — **Unified AINL + OpenClaw monitoring** (token budget, weekly trends, cron, sentinel, **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, env vars, troubleshooting). **OpenClaw MCP skill:** [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) · **ZeroClaw:** [`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md) (`~/.zeroclaw/`, not OpenClaw daily memory)
- [`AUTONOMOUS_OPS_PLAYBOOK.md`](AUTONOMOUS_OPS_PLAYBOOK.md) — current autonomous ops reality
- [`AUTONOMOUS_OPS_MONITORS.md`](AUTONOMOUS_OPS_MONITORS.md) — monitor index
- [`STANDARDIZED_HEALTH_ENVELOPE.md`](STANDARDIZED_HEALTH_ENVELOPE.md) — common message envelope
- [`RUNTIME_CONTAINER_GUIDE.md`](RUNTIME_CONTAINER_GUIDE.md) — running AINL services in containers
- [`SANDBOX_EXECUTION_PROFILE.md`](SANDBOX_EXECUTION_PROFILE.md) — sandbox execution profile and constraints
- [`EXTERNAL_ORCHESTRATION_GUIDE.md`](EXTERNAL_ORCHESTRATION_GUIDE.md) — orchestrating AINL from external systems (includes MCP agent role templates, desktop-safe recipe, and end-to-end validator/inspector/runner example)
- [`BATCH_AUTOMATION_GUIDE.md`](BATCH_AUTOMATION_GUIDE.md) — batch issue-solving and Dispatch-style repo automation: inspect-first, worktree-safe, deterministic, auditable

## Related sections

- Adapters and host bindings: [`../adapters/README.md`](../adapters/README.md)
- Example support framing: [`../examples/README.md`](../examples/README.md)
- Case studies: [`../case_studies/README.md`](../case_studies/README.md)
