# From LangGraph to AINL in 15 minutes

If you already think in **graphs** and **tool nodes**, AINL should feel familiar — with one shift: the **workflow is a compact program** that compiles to canonical IR, validates in **strict** mode, and runs deterministically without the model sitting in the control plane on every invocation.

## What you keep

- Explicit **nodes**, **edges**, branching, and tool-like **R** steps.
- A clear **entry** and **exit** story (AINL enforces single-exit discipline in strict mode).
- The option to **emit LangGraph** when you need that ecosystem today (`--emit langgraph`).

## What changes

- You **author** (or have an LLM author) **AINL source**, not Python `StateGraph` boilerplate.
- The **compiler** checks reachability, adapter contracts, and dataflow — something prompt-looped LangGraph code paths do not give you for free.
- **Compile-once / run-many**: after compile, execution does not re-spend tokens on orchestration logic.

## 15-minute path

1. Read **[Hybrid guide](../HYBRID_GUIDE.md)** — why AINL + hybrid emit exists.
2. Open **`examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl`** — small deterministic slice.
3. Run strict validate + emit:

   ```bash
   python3 scripts/validate_ainl.py --strict examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl \
     --emit langgraph -o /tmp/monitoring_langgraph.py
   ```

4. Compare token size of the **`.ainl`** file vs the emitted **`.py`** using your usual tokenizer or the repo’s **`make benchmark`** / **`BENCHMARK.md`** methodology.
5. Keep **`.ainl`** in git as the **source of truth**; treat emitted Python as a build artifact when you need LangGraph deployment.

## When to stay on LangGraph-only

- You need **only** LangGraph runtime features with no interest in multi-target emission or strict compile guarantees.
- Your team never wants a **non-Python** authoring surface.

## Related

- **[AINL + Temporal](AINL_AND_TEMPORAL.md)** — durability without giving up AINL as source.
- **[Benchmarks hub](../benchmarks.md)** / **[Size tables (repo root)](../../BENCHMARK.md)** — size and runtime evidence.
- Runner discovery for MCP hosts: HTTP **`GET /capabilities/langgraph`** on **`scripts/runtime_runner_service.py`**.
