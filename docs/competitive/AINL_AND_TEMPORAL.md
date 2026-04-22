# AINL + Temporal: best of both worlds

**Temporal** gives you **durable execution**, retries, and worker infrastructure. **AINL** gives you a **compact authoring surface**, **strict validation**, and **canonical graph IR** that compiles once and runs many times without the LLM re-deriving control flow on every run.

You do not have to pick one: from **v1.2.5**, validate can emit Temporal-shaped Python modules from the same IR that powers the core runtime (**current release: v1.7.1**).

## How it fits

1. **Author** operational workflows in **AINL** (monitors, token trackers, SLA checks, bridge-driven workers).
2. **Compile** with **`--strict`** so reachability and adapter contracts are checked before production.
3. **Emit** when you need Temporal’s worker model:

   ```bash
   python3 scripts/validate_ainl.py --strict path/workflow.ainl --emit temporal -o ./out/prefix
   ```

   See **`docs/hybrid_temporal.md`** and **`examples/hybrid/temporal_durable_ainl/`** for the intended layout.

4. **Run** activities/workflows with Temporal’s test or production environment; keep **`.ainl`** as the **single source of truth** and regenerate emit when the graph changes.

## What AINL is not replacing

- Temporal’s **server**, **namespaces**, **visibility**, and **worker scaling** — still Temporal’s job.
- Long-lived **human-in-the-loop** conversational state — out of scope for strict operational graphs (use adapters + explicit frames).

## Tests in this repo

- Optional **`temporalio`** integration tests emit and exercise emitted code (see **`tests/test_hybrid_emit_integration.py`**).

## Related

- **[Hybrid guide](../HYBRID_GUIDE.md)** — full hybrid story (LangGraph + Temporal + `S hybrid` hints).
- Runner discovery: **`GET /capabilities/temporal`** on the HTTP runner.
- **[From LangGraph to AINL](FROM_LANGGRAPH_TO_AINL.md)** — onboarding from graph-first Python frameworks.
