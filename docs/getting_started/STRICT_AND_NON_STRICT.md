# Strict vs non-strict validation

AINL has **two compile policies**. You choose which one fits your stage of work.

## Non-strict (default)

- **`ainl-validate file.ainl`**, **`ainl run …`**, and **`AICodeCompiler()`** without `strict_mode=True` use the **permissive** policy.
- More graphs compile (compatibility syntax, softer adapter checks, fewer dataflow guarantees).
- Best for **exploration**, **teaching**, **rapid iteration**, and **large example trees** where not every file is meant to be “production-tight.”

## Strict (opt-in)

- **CLI:** add **`--strict`** to **`ainl-validate`** / **`scripts/validate_ainl.py`** (and related flags such as **`--strict-reachability`** where documented).
- **API:** **`AICodeCompiler(strict_mode=True, …)`** (see also **`--strict`** behavior in [`../INSTALL.md`](../INSTALL.md)).
- Enforces the **stricter** rules in [`../AINL_SPEC.md`](../AINL_SPEC.md) §3.5-style validation: graph shape, reachability, adapter contracts, clearer dataflow, quoted-vs-bare literal rules, and related diagnostics.
- Best when you want **CI gates**, **reviewable production graphs**, or **emitter targets** that assume a canonical graph.

Strict and **runtime execution mode** (`graph-preferred`, `steps-only`, …) are **orthogonal**: strict is about **compile-time** guarantees; execution mode is about **how** the runtime walks the IR.

## Choosing

| Situation | Suggestion |
|-----------|------------|
| Learning or sketching workflows | Non-strict |
| Shipping a workflow you rely on | Turn on strict locally, then in CI |
| Teaching / demos in `demo/` and `examples/` | Often non-strict; some files are **intentionally** not strict-clean (e.g. error demos) |

## This repository

- Many files under **`demo/`** and **`examples/`** are maintained to **compile in non-strict** mode for breadth and teaching.
- **Strict** is still recommended for **your own** production programs when you want the strongest static checks.

**See also:** [`../CONFORMANCE.md`](../CONFORMANCE.md) (matrix and tooling), [`../INSTALL.md`](../INSTALL.md) (validator flags and diagnostics), [`../AINL_SPEC.md`](../AINL_SPEC.md) §3.5 (strict rules).
