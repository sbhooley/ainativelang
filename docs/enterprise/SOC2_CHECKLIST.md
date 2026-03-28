# SOC 2 alignment checklist (stub)

This document is a **working stub** for teams mapping AINL deployments to common SOC 2 (Trust Services Criteria) expectations. It is **not legal or compliance advice**. Final control design and evidence are your responsibility and should be reviewed with your auditor.

## Purpose

- Give security and GRC teams a starting list of questions when AINL appears in the control boundary.
- Tie product behaviors (policy gates, execution tape, compiler validation) to audit-friendly language.

## Status

| Area                         | Stub state |
|-----------------------------|------------|
| CC6 — logical access        | Draft bullets below |
| CC7 — system operations     | Draft bullets below |
| CC8 — change management     | Draft bullets below |
| A1 — availability (optional)| Not started |

## Draft mapping notes

- **Immutable audit trail:** JSONL execution tape from the runtime; pair with log retention and access controls in your environment.
- **Change control:** Treat compiled `.ainl` / graph IR as versioned artifacts; `ainl check --strict` in CI as a gate before promote.
- **Policy gates:** Document which capability grants and gates apply to adapters (email, HTTP, secrets) per environment.
- **Hosted runner / commercial:** For SLA-backed or managed execution, see [COMMERCIAL.md](../../COMMERCIAL.md) and your order form.

## Next steps

1. Expand each criterion with your org’s actual controls (IdP, secrets store, SIEM).
2. Add references to `docs/validation-deep-dive` (or site equivalent) for reachability and diagnostics.
3. Replace this stub with a version reviewed by counsel or a SOC 2 advisor before customer-facing “certification” claims.
