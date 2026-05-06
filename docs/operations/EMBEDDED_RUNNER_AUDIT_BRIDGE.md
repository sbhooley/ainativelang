# RFC: Optional runner-shaped audit from embedded `RuntimeEngine` (design only)

## Problem

Today, **structured JSON audit events** (`run_start`, `adapter_call`, `run_complete`, `run_failed`, `policy_rejected`) are emitted by the **HTTP runner service** on the `ainl.runner` logger ([`AUDIT_LOGGING.md`](AUDIT_LOGGING.md)). Paths that embed **`RuntimeEngine` directly** (CLI `ainl run`, MCP `ainl_run`, tests) **do not** emit that schema by default ([`AUDIT_AND_TELEMETRY_MAP.md`](AUDIT_AND_TELEMETRY_MAP.md)).

Enterprise buyers often want **one** pipeline shape for SIEM correlation. Marketing may still say “JSONL audit tape” broadly.

## Goal (non-binding)

Optionally emit **runner-equivalent** records (same field semantics and **redaction rules** as [`AUDIT_LOGGING.md`](AUDIT_LOGGING.md)) when:

- a host enables an explicit flag / env (e.g. `AINL_EMBEDDED_RUNNER_AUDIT=1` or MCP tool option), and
- a sink is configured (structured logger handler, or JSONL file).

## Constraints (must hold before implementation)

1. **Redaction parity** with runner audit: no raw adapter results; args redacted; error truncation rules identical.
2. **No silent doubling**: if both runner and embedded bridge emit, document dedupe keys (`trace_id`).
3. **Performance**: must not materially slow hot path; allow async/buffered sink.
4. **Schema versioning**: add `schema_version` field if event shape evolves.

## Out of scope for this RFC

- Replacing trajectory JSONL (different purpose).
- Claiming SOC 2 certification.

## Status

**Design / RFC only** — no runtime behavior change is implied by this file. Implement only after product + security review.
