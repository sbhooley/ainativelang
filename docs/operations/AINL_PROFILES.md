# Named AINL profiles (multi-host scale)

**Goal:** One **portable core** with **named bundles** of environment defaults so thousands of installs do not each invent a one-off matrix of `AINL_*` variables.

Profiles live in **`tooling/ainl_profiles.json`** (versioned with the repo). They are **hints**, not a substitute for reading [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) and measuring your workload.

## Built-in profiles

| Id | Intent |
|----|--------|
| `dev` | Local iteration: IR cache + embedding stub |
| `staging` | Pre-prod: adds conservative intelligence merge policy |
| `openclaw-default` | Baseline for OpenClaw + bridge wrappers + intelligence |
| `cost-tight` | Stricter bridge report cap + same conservative defaults |

## What the profiles set (startup token + embedding enablement)

- `AINL_STARTUP_CONTEXT_TOKEN_MIN` / `AINL_STARTUP_CONTEXT_TOKEN_MAX` (startup bootstrap allocation clamps)
  - `openclaw-default`: max ~`800`
  - `cost-tight`: max ~`500`
- `AINL_STARTUP_USE_EMBEDDINGS=1`
  - Embedding top-k candidates are only used when `AINL_EMBEDDING_MODE != stub`
  - If `AINL_EMBEDDING_MODE=stub`, startup falls back to the deterministic `MEMORY.md`-based selection path.

If you opt into real vectors, also index first via the embedding pilot wrapper (see [`EMBEDDING_RETRIEVAL_PILOT.md`](EMBEDDING_RETRIEVAL_PILOT.md)).

## CLI

```bash
ainl profile list
ainl profile show openclaw-default
ainl profile show cost-tight --json
# Shell (bash/zsh): apply for current session
eval "$(ainl profile emit-shell openclaw-default)"
```

**Do not** commit secrets into profiles. Gateway-only variables (`PROMOTER_LLM_*`) stay on the Apollo process; document them in staging runbooks, not in shared JSON.

## Philosophy

- **Profiles** = safe defaults + staging order reminders (**notes** field).
- **Hosts** (OpenClaw, ZeroClaw, bare MCP) = installers + paths + cron; see [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md).
- **Isolation** = separate DBs and workspaces per tenant/user; see [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md).
- **Agent + AINL** = who owns what and the default loop; see [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md).

## See also

- [`OPENCLAW_AINL_GOLD_STANDARD.md`](OPENCLAW_AINL_GOLD_STANDARD.md) — full OpenClaw install/upgrade checklist (profiles, caps, cron, verification)
- [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md)
- [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md)
- [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md)
- [`../getting_started/HOST_MCP_INTEGRATIONS.md`](../getting_started/HOST_MCP_INTEGRATIONS.md)
