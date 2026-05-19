# Competitive LangGraph baselines

Hand-written **LangGraph** equivalents for head-to-head **authoring token** comparisons against strict-valid `.ainl` sources.

| File | AINL source | Hand-optimized Python sibling |
|------|-------------|-------------------------------|
| [`enterprise_monitor_langgraph.py`](enterprise_monitor_langgraph.py) | [`examples/benchmark/enterprise_monitor.ainl`](../../../examples/benchmark/enterprise_monitor.ainl) | [`authoring_density/enterprise_monitor.py`](../authoring_density/enterprise_monitor.py) |
| [`support_ticket_router_langgraph.py`](support_ticket_router_langgraph.py) | [`examples/workflows/support_ticket_router.ainl`](../../../examples/workflows/support_ticket_router.ainl) | [`authoring_density/support_ticket_router.py`](../authoring_density/support_ticket_router.py) |

## Regenerate token counts

```bash
python scripts/benchmark_competitor_baselines.py
```

Output: [`tooling/competitor_baseline_tokens.json`](../../../tooling/competitor_baseline_tokens.json) — consumed by [`docs/competitive/COMPARISON_TABLE.md`](../../../docs/competitive/COMPARISON_TABLE.md).

## Equivalence notes

- LangGraph baselines include **graph boilerplate** (StateGraph, nodes, conditional edges) that `.ainl` compiles away into IR.
- **Runtime LLM call counts** match the hand-optimized Python baselines (same classify/route/draft semantics).
- These are **authoring-size** comparisons, not claims about LangGraph worker latency vs AINL runtime.

## Dependencies

```bash
pip install langgraph httpx openai
```

Optional: run equivalence smoke against Python baseline (requires network/API keys for LLM nodes):

```bash
python benchmarks/handwritten_baselines/competitive/langgraph/enterprise_monitor_langgraph.py
```
