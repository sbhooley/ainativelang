# AI Native Lang (AINL) for OpenClaw - Integration Guide

This document sketches how to expose **OpenClaw actions** as AINL adapters so that AINL programs can drive OpenClaw workflows.

**Before implementation work:** Agents and contributors should follow **`../BOT_ONBOARDING.md`** and complete **`../OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** (see `tooling/bot_bootstrap.json`).

**OpenClaw MCP skill (host config):** **`skills/openclaw/`**, **`ainl install-openclaw`**, **`~/.openclaw/openclaw.json`** (`mcp.servers.ainl`), stdio **`ainl-mcp`** — see **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)**. This is **separate** from **`ocl.*`** adapter bindings and **`openclaw/bridge/`** cron runners below.

**ZeroClaw:** integrate via the **ZeroClaw skill**, **`ainl install-zeroclaw`**, and stdio **`ainl-mcp`** — see **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)**. This guide documents **`ocl.*`** adapter patterns for **OpenClaw** hosts; ZeroClaw does not require the OpenClaw bridge layout.

---

## 1. Design

- AINL adapters are the bridge between the **graph IR** and the **host environment**.
- For OpenClaw, we treat each high-level action (e.g. "send email", "create CRM record", "run SEO check") as an adapter verb.
- The adapter registry (see `../ADAPTER_REGISTRY.md`) is extended with an `ocl` (OpenClaw) namespace.

Example naming:

- `ocl.Email.Send`
- `ocl.CRM.UpsertLead`
- `ocl.SEO.AuditPage`

The AINL layer remains unchanged; only the adapter registry and runtime bindings grow.

---

## 2. Exposing OpenClaw actions

1. **Define adapter verbs** for each OpenClaw capability:

   ```text
   R ocl.Email.Send to_addr subject body ->result
   R ocl.CRM.UpsertLead lead_payload ->lead
   ```

2. In the OpenClaw runtime:

   - Implement an `AdapterRegistry` entry for `ocl`.
   - Map each verb to the corresponding OpenClaw API / SDK call.
   - Ensure effect typing (`io-write` for mutating actions, `io-read` for queries).

3. Update the adapter manifest to describe:

   - Input schema: required fields and types.
   - Output schema: structure of `result` / `lead`.
   - Side-effect description (for policy validators).

---

## 3. Writing AINL programs that trigger OpenClaw

Example: "When a new lead is created, send a welcome email and log an event."

```text
S core web /api
E /leads G ->L_lead ->lead

L_lead:
  R db.C Lead * ->lead
  R ocl.Email.Send lead.email "Welcome" "Thanks for signing up" ->email_result
  R ocl.CRM.UpsertLead lead ->crm_lead
  J lead
```

The AINL compiler emits a graph; the OpenClaw runtime wires `ocl.*` nodes into actual OpenClaw actions.

---

## 4. Policy validation for OpenClaw

Use `tooling/policy_validator.py` to enforce workspace-level constraints, such as:

- "No `ocl.Email.Send` in this workspace."
- "Only read-only `ocl.*` verbs allowed when running in preview mode."

Example policy:

```python
policy = {
  "forbidden_adapters": ["http"],    # e.g. no raw HTTP
  "forbidden_effect_tiers": ["io-write"]
}
```

An OpenClaw-specific policy layer can add finer-grained checks based on `node.data`.

---

## 5. Generating AINL from English (OpenClaw workflows)

A simple reasoning chain for small models:

1. **Classify** the request:
   - "Is this a web endpoint, cron job, scraper, or pure OpenClaw action?"
2. **Select a template**:
   - For web/cron/scraper, start from examples in `examples/`.
   - For OpenClaw actions, start from a minimal `S core web` or `S core cron` skeleton plus `R ocl.*` calls.
3. **Fill slots**:
   - Map English fields to adapter slots (`to_addr`, `subject`, `body`, `lead_payload`, etc.).
4. **Compile and validate**:
   - Run the compiler.
   - If there are errors, use the structured messages and suggestions to fix them.
5. **Optionally apply patches**:
   - Use `tooling/ir_compact.py` and `tooling/ir_compact_patch.py` to propose minimal graph edits.

This keeps the integration **transparent and auditable**: AINL describes the workflow; OpenClaw performs the actions; policy and oversight guardrails run on the IR and traces.

---

## 6. Related: production bridge runner & monitoring

For the **shipped** OpenClaw bridge (cron payloads, `run_wrapper_ainl.py`, daily markdown memory, token-budget and weekly-trends wrappers), read:

- [`../ainl_openclaw_unified_integration.md`](../ainl_openclaw_unified_integration.md) — integration boundaries and env vars; **`openclaw_token_tracker`** (main-session token snapshot + optional `openclaw cache`); **`content-engine`** **`model_override`** and **critical** wrapper behavior under budget guards
- [`../operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md) — unified monitoring (memory path **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, sentinel, consolidated notify)
- [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md) — bridge tools table and cron examples
- [`../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](../openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md) — token budget wrapper reference
- [`../CRON_ORCHESTRATION.md`](../CRON_ORCHESTRATION.md) — drift checks and registry discipline
