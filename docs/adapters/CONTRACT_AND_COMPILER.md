# Adapter contract vs compiler (AINL)

## Two different “ok” signals

- **Compiler / `ainl validate` / `ainl compile`** — graph shape, opcodes, strict policy, and manifest-declared **adapter names** and **verb spellings** the compiler knows about. Success means the IR is structurally valid for this toolchain, not that every `R adapter.VERB` matches a hand-written “how to call this HTTP endpoint” document.
- **Adapter contract (MCP)** — human-oriented semantics: typical arguments, pitfalls, and links to `ainl://` resources. The deterministic bundle is built from `tooling/ainl_get_started.py` (`ADAPTER_CONTRACTS`) and is exposed as `ainl_adapter_contract` and `ainl://adapter-contracts`.

## Versioned `adapter_contract` payload

The MCP `ainl_adapter_contract` tool returns a JSON object that includes:

- `schema_version` — **string** (see `ADAPTER_CONTRACT_PAYLOAD_SCHEMA_VERSION` in `tooling/ainl_get_started.py`).
- `adapter`, `status`, `summary` — as before.
- `verbs` — per-verb entries where documented (per-adapter shape varies; see bundle).
- `strict_valid_pointers` (for `http` / `fs` when applicable) — links into CI `strict-valid` and/or honest notes when no profiled example exists.
- `runtime_registration` — reminder of the MCP `adapters` object for `ainl_run`.
- `pitfalls` — authoring mistakes.

`ainl://adapter-contracts` is a JSON object keyed by bundle name, same payloads.

## Single source of truth for “what verbs exist at runtime”

- **Full runtime catalog** — `tooling/adapter_manifest.json` and `ainl_capabilities` (merged into `strict_summary` for fast checks).
- **MCP / wizard bundle** — `ADAPTER_CONTRACTS` in `tooling/ainl_get_started.py` (imported by the MCP server for hints). New verbs should appear in the manifest and, where agents need prose examples, in `ADAPTER_CONTRACTS` — not only in `AGENTS.md` prose.

## Optional validate/compile warnings: `contract_alignment`

On successful `ainl_validate` / `ainl_compile`, the MCP server may add:

- `contract_alignment` — `schema_version`, `severity: "warning"`, `items[]` for **http** and **fs** `R` lines whose verb token is **not** in `ADAPTER_CONTRACTS`. These are **non-fatal**: the runtime may have newer verbs; use `ainl_capabilities` as the final arbiter.

## Related

- `AGENTS.md` (HTTP `R` line rules, queue, strict-valid lists).
- `docs/EXAMPLE_SUPPORT_MATRIX.md` and `tooling/artifact_profiles.json` for CI `strict-valid` paths.
