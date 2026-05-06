# Integrations — agent protocols, HTTP commerce, and bridges

Canonical **wire + security** docs for outbound agent integrations live in this folder. Read **`AGENTS.md`** (repo root) first for HTTP `R` line rules, queue forms, and strict example policy.

## MCP host integrations (OpenClaw / ZeroClaw / Hermes)

| Doc | What it covers |
|-----|----------------|
| **[`MCP_HOSTS.md`](./MCP_HOSTS.md)** | Single guide for installing AINL as an MCP-native skill in **OpenClaw**, **ZeroClaw**, and **Hermes**. Per-host install paths, bridges, ZeroClaw bridge monitoring wrappers, and the Hermes closed learning loop. Replaces the previous per-host docs (now stub redirects). |
| **[`hermes-agent.md`](./hermes-agent.md)** | Hermes Agent — marketing-style intro for the integrations index; deep-dive lives in `MCP_HOSTS.md#hermes`. |

## IDE / developer workflows

| Doc | What it covers |
|-----|----------------|
| **[`CURSOR_GRAPH_MEMORY.md`](./CURSOR_GRAPH_MEMORY.md)** | **Plan & tracker:** Cursor chat artifacts → strict AINL pipelines → graph memory / ArmaraOS inbox; reproducibility, phases, competitive framing, deliverables. |

## Agent protocols & commerce (HTTP and beyond)

| Doc | What it covers |
|-----|----------------|
| **[`HTTP_MACHINE_PAYMENTS.md`](./HTTP_MACHINE_PAYMENTS.md)** | **x402** + **MPP** on **`http`** (`payment_profile`, structured `402`, `http_payment` merges), landscape table (**AP2**, **ACP** checkout, **AGTP**), repo placement (“where to put other protocols”). |
| **[`AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md`](./AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md)** | Honest **“can I ship today?”** matrix + **G1–G7** backlog (examples, AP2/ACP guides, signing helpers, education). |
| **[`AGTP.md`](./AGTP.md)** | **AGTP** is not plain `http` — **HTTP gateway**, **MCP/daemon**, future **`agtp` adapter**, or **`shell_exec`** paths. |
| **[`A2A_ADAPTER.md`](./A2A_ADAPTER.md)** | **A2A** (Agent-to-Agent) client adapter — **not** Stripe ACP checkout; SSRF/allowlist contract. |

## Security

Outbound **`http`** and **`a2a`** are network-capable surfaces. Start at **[`../../SECURITY.md`](../../SECURITY.md)** (reporting + sensitive areas).

## Examples

Strict vs non-strict example policy: **`examples/README.md`**, **`docs/EXAMPLE_SUPPORT_MATRIX.md`**, and **`tooling/artifact_profiles.json`**.

**Local machine-payment demo (no external paywall):** from the repo root, run **`python scripts/run_http_machine_payment_roundtrip_demo.py`** (uses **`examples/http/http_machine_payment_flow_compact.ainl`**).
