# Enterprise shared responsibility (AINL)

This document is the **canonical boundary** between what the **AINL language, compiler, and open-source Python runtime** provide versus what **your organization** must operate when AINL sits inside a regulated or enterprise control boundary.

It is **not legal or compliance advice** and does **not** imply SOC 2, ISO, HIPAA, or GDPR certification for the AINL project or repository.

## Related documentation

- **Which log / JSONL surfaces exist:** [`../operations/AUDIT_AND_TELEMETRY_MAP.md`](../operations/AUDIT_AND_TELEMETRY_MAP.md)
- **RFC (optional runner-shaped audit from embedded runs):** [`../operations/EMBEDDED_RUNNER_AUDIT_BRIDGE.md`](../operations/EMBEDDED_RUNNER_AUDIT_BRIDGE.md) — design only
- **HTTP runner structured audit schema:** [`../operations/AUDIT_LOGGING.md`](../operations/AUDIT_LOGGING.md)
- **Operator SOC 2 checklist (mapping starter):** [`SOC2_CHECKLIST.md`](SOC2_CHECKLIST.md)
- **TSC-style control mapping (language + runtime vs operator):** [`../operations/AINL_SOC2_CONTROL_MAPPING.md`](../operations/AINL_SOC2_CONTROL_MAPPING.md)
- **Repo reality vs aspirational product lines:** [`../../STATUS.yaml`](../../STATUS.yaml)
- **Commercial terms and offerings:** [`../../COMMERCIAL.md`](../../COMMERCIAL.md)

## For enterprise security reviews

- **Threat model and safe-use assumptions (coordination / local-first patterns):** [`../advanced/SAFE_USE_AND_THREAT_MODEL.md`](../advanced/SAFE_USE_AND_THREAT_MODEL.md)
- **Provenance and release evidence (supply chain / reproducibility narrative):** [`../PROVENANCE_AND_RELEASE_EVIDENCE.md`](../PROVENANCE_AND_RELEASE_EVIDENCE.md)

## What AINL provides (typical)

| Area | In-repo / product behavior |
|------|----------------------------|
| **Determinism** | Compiled IR and documented runtime semantics; optional strict static checks (`ainl check --strict`). |
| **Explicit effects** | Adapter calls and graph structure are reviewable artifacts; capability and policy patterns are documented. |
| **Evidence primitives** | Multiple **separate** surfaces: HTTP runner JSON (`ainl.runner`), CLI trajectory JSONL (`--trace-jsonl` / `--log-trajectory`), optional `audit_trail` adapter, optional metrics JSONL. See the telemetry map. |
| **Integrity helpers** | `audit_trail` records include a deterministic `event_hash`; CLI includes `ainl audit verify-jsonl` to re-check those lines. |

## What the customer / operator owns (typical)

| Area | Why it stays on your side |
|------|-----------------------------|
| **Identity and access** | Who may change graphs, call runners, or use MCP hosts; IdP, RBAC, API keys, rotation. |
| **Network and platform** | TLS termination, segmentation, secrets stores (Vault, cloud KMS), container and VM hardening. |
| **Log lifecycle** | Immutable or WORM storage, retention, legal hold, SIEM routing, access control to trace files—**your** log platform. |
| **SOC 2 / ISO / HIPAA / GDPR programs** | Policies, HR, vendors, DPIAs, BAAs, auditor evidence **packages** assembled from **your** environment plus AINL artifacts. |
| **Change management** | Git, CI gates, promotion to production—often mapped to CC8-style expectations alongside `ainl check --strict` output. |

## Boundaries (what open-source AINL does not ship)

To avoid mismatch between **marketing language** and **repository reality**, treat the following as **out of scope for the OSS repo** unless explicitly shipped and listed in [`STATUS.yaml`](../../STATUS.yaml) under `real_and_working` or `telemetry_and_audit_surfaces`:

- **SOC 2 (or other) attestation** for the AINL open-source project itself.
- **Managed multi-tenant hosted execution** or **cloud-hosted validation with compliance dashboards** as a shipped OSS product—the repo documents several commercial / SaaS directions under **`aspirational_not_built`**, including for example **`hosted_runtime_saas`**, **`validation_saas_dashboard`**, **`cloud_marketplace_api`**, **`token_gating`**, **`marketplace_graphs`**. See [`STATUS.yaml`](../../STATUS.yaml) for the current list.
- **A single unified “compliance product”** that replaces your SIEM, log store, or GRC tooling.

**Commercial** offerings (if any) are described separately—see [`COMMERCIAL.md`](../../COMMERCIAL.md)—and may address support SLAs or packaged services; they do not change the shared-responsibility split for self-hosted open-core use.

## Evidence bundles (operational)

For a **copy-paste runbook** to assemble artifacts for security or audit conversations, see [`EVIDENCE_BUNDLE_RECIPE.md`](EVIDENCE_BUNDLE_RECIPE.md).
