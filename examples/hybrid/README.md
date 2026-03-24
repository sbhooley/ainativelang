# Hybrid examples (AINL as deterministic core)

This folder holds **interop demos**: keep policy, branching, and adapter calls in **AINL**, while a host framework handles orchestration, durability, or agent loops.

## Why use AINL as the deterministic core?

- **Lower token cost** — You compile the graph once; `RuntimeEngine` runs it without re-spending LLM tokens on orchestration for the AINL-authored portion.
- **Strict guarantees** — Optional strict compile checks (adapter contracts, dataflow) catch mistakes before production.
- **Auditability** — Graph-shaped IR, trajectory hooks, and explicit `R` adapter steps are easier to review than ad hoc imperative glue.

## Patterns

| Pattern | What wraps AINL | Example |
|--------|------------------|---------|
| **LangChain tools** | `langchain_tool` adapter from user code / workers | [`langchain_tool_demo.ainl`](langchain_tool_demo.ainl) |
| **LangGraph** | `StateGraph` with one node calling `run_ainl_graph` | [`langgraph_outer_ainl_core/`](langgraph_outer_ainl_core/) |
| **Temporal** | Activity + workflow calling `execute_ainl_activity` | [`temporal_durable_ainl/`](temporal_durable_ainl/) |

## Quick links

- **LangGraph hybrid** — [`langgraph_outer_ainl_core/README.md`](langgraph_outer_ainl_core/README.md) · [`docs/hybrid_langgraph.md`](../../docs/hybrid_langgraph.md)
- **Temporal hybrid** — [`temporal_durable_ainl/README.md`](temporal_durable_ainl/README.md) · [`docs/hybrid_temporal.md`](../../docs/hybrid_temporal.md)
- **CrewAI / LangChain tools** — enable `--enable-adapter langchain_tool` and see [`langchain_tool_demo.ainl`](langchain_tool_demo.ainl); adapter reference in [`docs/reference/ADAPTER_REGISTRY.md`](../../docs/reference/ADAPTER_REGISTRY.md)

## Decision help

See the one-page guide **[`docs/HYBRID_GUIDE.md`](../../docs/HYBRID_GUIDE.md)** (pure AINL vs LangGraph vs Temporal).

To include LangGraph and/or Temporal in benchmark **`minimal_emit`** slices (without using **`full_multitarget`**), add **`S hybrid langgraph`**, **`S hybrid temporal`**, or both at the top of your `.ainl` source — see the guide.

**Optional Python deps** for running emitted LangGraph / Temporal modules: `pip install -e ".[interop]"` from the repo root — details in **[`docs/PACKAGING_AND_INTEROP.md`](../../docs/PACKAGING_AND_INTEROP.md)**.
