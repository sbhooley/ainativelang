# AINL as deterministic core inside LangGraph

This folder shows a **hybrid** layout: **LangGraph** owns orchestration (checkpointing, multi-agent routing, optional LLM nodes), while **AINL** holds the **compact, deterministic** policy graph (no recurring tokens for the AINL-authored portion at runtime).

## Files

- **`monitoring_escalation.ainl`** — example workflow (strict-safe): threshold diff + summary string.
- **`monitoring_escalation_langgraph.py`** — emitted wrapper (regenerate with the command below).

## Regenerate the LangGraph wrapper

From the repository root:

```bash
python3 scripts/validate_ainl.py \
  examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl \
  --emit langgraph \
  -o examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation_langgraph.py
```

## Run the emitted graph

Requires `langgraph` (`pip install langgraph`). Run from repo root so `runtime/` and `adapters/` resolve:

```bash
python3 examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation_langgraph.py
```

The default graph is **START → `ainl_core` → END**, where `ainl_core` calls `run_ainl_graph()` with the embedded IR. Pass initial frame variables via LangGraph state under **`ainl_frame`** (e.g. `app.invoke({"ainl_frame": {"metric_value": 100}})` after you extend the AINL program to read those vars).

## Learn more

- [`docs/hybrid_langgraph.md`](../../../docs/hybrid_langgraph.md)
