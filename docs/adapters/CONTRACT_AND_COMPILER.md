# Adapter contracts and compiler integration

This document describes how adapter semantic contracts work, where they live, and how contributors should extend them when adding or modifying adapter verbs.

## Architecture

```
ADAPTER_CONTRACTS (tooling/ainl_get_started.py)
    ↓
contract_semantics.py (tooling/)
    ↓
ainl validate --strict-contracts
    ↓
Structured diagnostics (kind, severity, suggested_fix)
```

## Where contracts live

| Source | Role |
|--------|------|
| `tooling/ainl_get_started.py` → `ADAPTER_CONTRACTS` | Canonical dict of adapter verbs, arg specs, pitfalls |
| `tooling/adapter_manifest.json` | Machine-readable adapter catalog (name, effect, flags) |
| `tooling/contract_semantics.py` | Validation engine: IR → diagnostics |
| `runtime/adapters/base.py` | `ADAPTER_EFFECT` side-effect classification |

## Contributor checklist (adding or changing a verb)

1. **Add/update the verb entry** in `ADAPTER_CONTRACTS` (`tooling/ainl_get_started.py`).
   - Include `args` list with type annotations (required: `name: type`, optional: `name?: type`).
   - Include `example` showing compact syntax usage.
   - Include `returns` listing expected result fields.

2. **Update the adapter manifest** if adding a new adapter:
   - Add an entry to `tooling/adapter_manifest.json`.
   - Verify `ADAPTER_EFFECT` in `runtime/adapters/base.py` is consistent.

3. **Add a strict-valid example** if none exists for the adapter family:
   - Create under `examples/<adapter>/`.
   - Register in `tooling/artifact_profiles.json` under `strict-valid`.

4. **Test contract validation**:
   - Run `ainl validate <example> --strict --strict-contracts` and verify zero diagnostics.
   - Add negative test cases to `tests/test_strict_adapter_contracts.py` if the verb has arity constraints.

5. **Update MCP resource** (`ainl://adapter-contracts`) by running the MCP server — it reads `ADAPTER_CONTRACTS` at startup.

## Sync rules

- `ADAPTER_CONTRACTS` keys must be a superset of adapters referenced in `artifact_profiles.json` strict-valid examples.
- `adapter_manifest.json` adapter names should have a corresponding `ADAPTER_CONTRACTS` entry (gaps are tracked as "uncontracted" in `ainl_capabilities`).
- `ADAPTER_EFFECT` in `base.py` classifies side effects; contracts add verb-level semantic detail on top.

## Validation modes

| Flag | Behavior |
|------|----------|
| `--strict` | Syntax strictness (existing) |
| `--strict-contracts` | Semantic contract validation: unknown verbs and arity mismatches become errors |
| Neither | Permissive: compiles even with unknown verbs |

## See also

- [`docs/issues/04-strict-adapter-contract-expansion-policy.md`](../issues/04-strict-adapter-contract-expansion-policy.md) — expansion policy
- [`docs/operations/OPERATOR_MARKETING_GUARDRAILS.md`](../operations/OPERATOR_MARKETING_GUARDRAILS.md) — marketing rules
- [`docs/EMIT_TARGETS.md`](../EMIT_TARGETS.md) — shipped emit targets
