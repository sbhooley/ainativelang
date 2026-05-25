# Formal Verification PoC — Adapter Safety Properties

**Status:** Proof of concept. Opt-in via `ainl validate --verify-adapters`. Requires optional `z3-solver` dependency.

## Scope

This PoC proves a narrow set of safety properties about AINL IR graphs using Z3 constraint solving. It does **not** aim for full operational semantics or tensor type checking.

## Properties verified

| ID | Property | What it checks |
|----|----------|---------------|
| P1 | **Adapter allowlist** | Every adapter referenced in the IR is in the host's grant / allowlist |
| P2 | **No undeclared adapter refs** | Every `R` step references an adapter that appears in the IR's `adapters` or `meta` declarations |
| P3 | **Effect tier compliance** | No `write` or `side_effect` adapter is called from a label declared as `pure` |
| P4 | **DAG acyclicity** | The label call graph has no cycles (reuses existing compiler check; Z3 redundancy) |

## Architecture

```
tooling/verification/z3_adapter_safety.py
    ↓
IR dict → Z3 constraints → sat/unsat
    ↓
Structured diagnostics (VerificationResult)
```

The verifier reads the compiled IR, extracts adapter references and label structure, and encodes safety properties as Z3 constraints. An `unsat` result means the property holds; a `sat` result means a counterexample exists (a path that violates the property).

## IR subset

The verifier operates on:
- `labels` — label names and their steps
- Steps with `op: R` — adapter and target references
- `meta` / `adapters` declarations — declared adapter set
- Host grant (passed as parameter) — the allowed adapter set

It does not interpret frame variables, conditional branches, or loop bodies beyond their adapter references.

## Usage

```bash
# CLI (opt-in)
ainl validate my_graph.ainl --strict --verify-adapters

# Programmatic
from tooling.verification.z3_adapter_safety import verify_adapter_safety
result = verify_adapter_safety(ir, host_allowlist={"core", "http", "fs"})
print(result.summary())
```

## Limitations

- Z3 is an optional dependency (`pip install z3-solver`). Without it, `--verify-adapters` is a no-op with a warning.
- The verifier does not model runtime frame values, LLM outputs, or conditional execution paths.
- Effect tier labels (`pure`, `read`, `write`) are inferred from `ADAPTER_EFFECT` in `runtime/adapters/base.py`; adapters not in that table are treated as `unknown`.
- This is a PoC for grant-aligned research. Do not claim "formally verified" for production graphs.

## Related

- [`docs/IR_SCHEMA.md`](IR_SCHEMA.md) — IR structure reference
- [`tooling/effect_analysis.py`](../../tooling/effect_analysis.py) — existing effect analysis
- [`tooling/contract_semantics.py`](../../tooling/contract_semantics.py) — semantic contract validation
- [`STATUS.yaml`](../../STATUS.yaml) — `aspirational_not_built.formal_verification_z3`
