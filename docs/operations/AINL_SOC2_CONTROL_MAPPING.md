# SOC2-style control mapping (TSC) — AINL language & runtime vs operator

This document maps common **AICPA Trust Services Criteria (TSC)** control themes to **what the AI Native Lang (AINL) language, compiler, and Python runtime provide** versus **what deployers and enterprises must own** in their environment, process, and monitoring stack. It is the **AINL** counterpart to **host-level** control mapping for [ArmaraOS](https://github.com/sbhooley/armaraos/blob/main/docs/operations/SOC2_CONTROL_MAPPING.md) (the agent operating system). Use this for **shared responsibility** statements and customer questionnaires. Align criterion IDs to the exact **TSC** publication year your auditor uses; numbering and labels can differ slightly by edition.

**Related in-repo:** [`AUDIT_LOGGING.md`](AUDIT_LOGGING.md) (HTTP runner JSON audit) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`CAPABILITY_GRANT_MODEL.md`](CAPABILITY_GRANT_MODEL.md) · [`../trajectory.md`](../trajectory.md) (CLI JSONL) · **Root** [`../SECURITY.md`](../SECURITY.md) (reporting policy) when present.

---

## Shared responsibility (summary)

AINL provides **deterministic, compiler-checked** execution semantics, **optional strict** static checks, **runtime policy** and limits in hosted shapes, and **observability surfaces** you can feed into a compliance program: the **HTTP runner** emits **structured JSON** for `/run` and `/enqueue` (`run_start`, `adapter_call`, `run_complete` / `run_failed`, `policy_rejected`); the CLI can emit **per-step trajectory JSONL**; the optional **`audit_trail`** adapter can append **hashed, redacted** JSONL records. **Multi-workspace** isolation is achieved by **configuration** of separate paths and databases (see `WORKSPACE_ISOLATION.md`), not a cloud tenant product.

**Organizational** access (e.g. org-wide IdP, SCIM), **network and host** hardening, **TLS** for every API entrypoint, **central log retention** in an **immutable** or WORM store, and **SIEM** correlation (including **caller identity** and **client IP** for every event) are typically **customer or operator** responsibilities. AINL does not ship a managed log aggregation, alerting, or identity service.

**Embedding `RuntimeEngine` directly** (e.g. CLI `ainl run`, tests, MCP) does **not** emit the HTTP runner’s structured audit schema by default; see `AUDIT_LOGGING.md`.

---

## CC6 — Logical and physical access controls

| Criterion (typical intent) | In AINL (language & runtime) | Operator / customer | Notes |
|----------------------------|-----------------------------|----------------------|--------|
| **CC6.1** — Logical access: software, infrastructure, architecture | Compile-time graph validation; optional strict mode; policy hooks for `/run` paths; adapter allow/deny and capability grant patterns in docs | How you deploy `ainl-runner-service`, who may call it, network segmentation | **No** first-class org/tenant IAM in the language runtime. |
| **CC6.2** — Register / authorize before system credentials | Runners and MCP sit behind **your** auth; API keys in env/config as you design | IdP, API gateway, key rotation, secrets manager | AINL consumes secrets from the **host**; it does not replace Vault/IdP. |
| **CC6.3** — Remove or deactivate access | Revoke keys and redeploy; rotate `ainl` process env | HR offboarding, automated key revocation in your control plane | |
| **CC6.4** — Physical access to facilities | *N/A* (software) | Device / facility security | |
| **CC6.5** — Logical access to protected information | Policy, FS sandbox (`AINL_FS_ROOT`), adapter boundaries; path isolation per workspace | Data classification, DLP, encryption of `AINL_MEMORY_DB` and artifacts | You define what data flows through `.ainl` and adapters. |
| **CC6.6** — Restrict logical access to sensitive data | Separate per-workspace DBs and roots when configured; never share `AINL_MEMORY_DB` across tenants (see `WORKSPACE_ISOLATION.md`) | OS permissions, database ACLs, backup scoping | Misconfiguration can still colocate paths — **enforcement** is **deployment**. |
| **CC6.7** — Restriction of data during transmission (e.g. encryption) | HTTPS when your runner uses it; adapter-specific TLS to external services | Terminate TLS at the edge, mTLS, cert lifecycle | **Stack**-level. |
| **CC6.8** — Malware and unauthorized software | Pinned dependencies in your process; vetted adapter images / bundles in **your** pipeline | SDLC, image signing, allowlisted `pip`/wheel sources | AINL does not scan your entire supply chain. |

---

## CC7 — System operations (detection, monitoring, response)

| Criterion (typical intent) | In AINL (language & runtime) | Operator / customer | Notes |
|----------------------------|-----------------------------|----------------------|--------|
| **CC7.1** — Detect and communicate anomalies and events | HTTP runner **structured** audit stream; `audit_trail` **append-only** JSONL with per-record hash; trajectory JSONL for CLI runs | Central logging, alerts, runbooks, correlation with user/IP at the gateway | Runner events include `trace_id`, `adapter`, `result_hash`; **enrich** with who called `/run` at your **API** layer. |
| **CC7.2** — Monitor system components | Counters, traces, and optional monitors in your deployment; runner logs are **one** signal | APM, uptime checks, SLOs on `ainl-runner-service` | |
| **CC7.3** — Evaluate security events | `policy_rejected` in runner stream; static diagnostics when using strict/validate | SIEM rules, SOC triage | **Detection** logic is largely **yours**. |
| **CC7.4** — Respond to security incidents and breaches | Deterministic replays and artifact IDs when you record them; disclosure via project **SECURITY** policy | IR plan, customer comms | **Language** supports auditability; **IR** is organizational. |
| **CC7.5** — Vulnerabilities and system defects (identify, log, track) | Versioned `ainl` on PyPI; follow project advisories; patch the interpreter and deps in your image | Vulnerability management, `pip audit`, base image updates | **Dependency** updates are **operator** cadence. |

---

## Suggested control ownership (matrix row)

| Control area | AINL (design) | Operator (run time) |
|--------------|---------------|---------------------|
| Deterministic / validated execution | Yes (compiler, IR) | Chooses strictness, entrypoints, and pins versions |
| Structured run audit (HTTP) | Yes (see `AUDIT_LOGGING.md`) | Hosts runner, ships logs to SIEM |
| Per-workspace isolation | Yes (convention + env) | Enforces `OPENCLAW_WORKSPACE` / `AINL_*` per tenant |
| Central IAM, WORM, 24/7 SOC | No | IdP, log archive, on-call |
| Host agent OS (ArmaraOS) controls | *Separate product* | See [ArmaraOS mapping](https://github.com/sbhooley/armaraos/blob/main/docs/operations/SOC2_CONTROL_MAPPING.md) |

---

## ArmaraOS vs AINL (where to look)

| Scope | Document |
|-------|----------|
| **Graph language, `ainl run`, runner HTTP audit, Python `RuntimeEngine`, workspace env** | This file (`AINL_SOC2_CONTROL_MAPPING.md`) |
| **Agent OS, WASM tools, Merkle kernel audit, desktop/daemon** | [ArmaraOS `SOC2_CONTROL_MAPPING.md`](https://github.com/sbhooley/armaraos/blob/main/docs/operations/SOC2_CONTROL_MAPPING.md) |

---

## Disclaimer

This is **not** legal or audit advice. A SOC2 report is issued for a **system description** and **control objectives** in scope; map this document to your auditor’s criteria list and to your **actual** deployment (runner-only, MCP, ArmaraOS-hosted graphs, and so on).
