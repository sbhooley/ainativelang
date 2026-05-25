# Operator and agent marketing guardrails

Rules for operators, autonomous agents (e.g. AINL King), and contributors when making public claims about AINL capabilities.

## Core rules

1. **Version numbers:** Only quote the version in [`pyproject.toml`](../../pyproject.toml). Do not market a version that has not been released.

2. **Emit targets:** Only claim an emit target exists if it appears in the `choices` list of `ainl emit --target` in [`cli/main.py`](../../cli/main.py). The authoritative list is also in [`STATUS.yaml`](../../STATUS.yaml) under `marketing_claims_boundary.emit_targets`.

3. **Cost claims:** Cite [`docs/COST_ESTIMATOR.md`](../COST_ESTIMATOR.md) and the reproducible benchmark scripts in `scripts/benchmark_*.py`. Always specify the baseline (A/B/C) per [`docs/CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md).

4. **WASM scope:** The WASM adapter (`R wasm.CALL`) calls pre-compiled modules. It is **not** a whole-graph WASM compiler. Do not claim "graphs compile to WebAssembly" or "run in the browser."

5. **Type checking scope:** The compiler validates syntax, adapter names, and basic arity under `--strict`. There is no tensor type system, shape checker, or formal type-theoretic verifier. Do not claim the compiler "rejects tensor/string mismatches" unless this changes in a future release with tests and STATUS.yaml promotion.

6. **Bare metal / machine code:** AINL compiles `.ainl` to IR JSON and executes via Python `RuntimeEngine`. There is no native codegen, no LLVM backend, no "bare metal" compilation. This claim is categorized as **never** in STATUS.yaml.

7. **STATUS.yaml is the source of truth:** Before tweeting, posting, or including a capability in a report, check `STATUS.yaml` → `marketing_claims_boundary`. If the feature is listed as `never`, `never_shipped`, or `aspirational`, do not present it as working.

## Claim checklist (per statement)

| Question | Required answer |
|----------|----------------|
| Is the feature in `real_and_working` or `marketing_claims_boundary` with status `shipped`? | Yes |
| Does the version match `pyproject.toml`? | Yes |
| Is the emit target in `cli/main.py` choices? | Yes (if claiming an emit target) |
| Is the baseline (A/B/C) specified for any cost/savings number? | Yes |
| Does a reproducible script or test prove the claim? | Yes |

## Integration hooks

- **AINL King cron prompts:** Inject a reference to this document in the AINL King system prompt or cron template so the agent self-checks claims before publishing. This is an operator-side configuration change (e.g. in OpenClaw workspace `INTEGRATION.md` or ArmaraOS agent manifest), not implemented in this repo.

- **Agent reports:** Files in [`agent_reports/`](../../agent_reports/) should include a disclaimer linking to this document when they contain capability claims. See [`agent_reports/README.md`](../../agent_reports/README.md).

- **Case studies:** [`docs/case_studies/`](../case_studies/) entries should link here when they contain forward-looking or capability-boundary statements.

## Anti-patterns (explicit "never" claims)

These will never be accurate for the current architecture:

- "Graphs compile to machine code / bare metal"
- "Full workflow runs as browser WASM / on-chain smart contract"
- "AINL replaces the Python runtime with native execution"
- Quoting a version ahead of `pyproject.toml`

## See also

- [`STATUS.yaml`](../../STATUS.yaml) — shipped vs aspirational vs never
- [`docs/CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) — claim-to-evidence crosswalk
- [`docs/COST_ESTIMATOR.md`](../COST_ESTIMATOR.md) — cost estimation methodology
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — contributor acknowledgment policy
