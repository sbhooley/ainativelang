# Integrations — agent protocols, HTTP commerce, and bridges

Canonical **wire + security** docs for outbound agent integrations live in this folder. Read **`AGENTS.md`** (repo root) first for HTTP `R` line rules, queue forms, and strict example policy.

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
