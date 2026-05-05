#!/usr/bin/env python3
"""
LangGraph-shaped version of the doc_pipeline vanilla baseline.

Nodes correspond to AINL pipeline steps; conditional edges encode the type-
dispatch that the compiled AINL handles with zero-token IR branches.  Logic
delegates to ``pure_async_python`` so the two baselines stay in sync.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict

_SUB = Path(__file__).resolve().parent
if str(_SUB) not in sys.path:
    sys.path.insert(0, str(_SUB))

from pure_async_python import (  # noqa: E402
    DocPipelineInput,
    DocPipelineOutput,
    MockLLM,
    run_compiled_pipeline,
    run_vanilla_pipeline,
)

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "langgraph is required for this baseline. "
        "Install with: pip install 'ainativelang[benchmark]' or pip install langgraph"
    ) from exc


class DocState(TypedDict, total=False):
    inp: DocPipelineInput
    llm: MockLLM
    output: DocPipelineOutput
    approach: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def node_run_pipeline(state: DocState) -> Dict[str, Any]:
    inp = state["inp"]
    llm = state.get("llm") or MockLLM()
    approach = state.get("approach", "vanilla")
    if approach == "compiled":
        output = await run_compiled_pipeline(inp, llm)
    else:
        output = await run_vanilla_pipeline(inp, llm)
    return {"output": output}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(approach: str = "vanilla") -> Any:
    g: StateGraph = StateGraph(DocState)
    g.add_node("run_pipeline", node_run_pipeline)
    g.add_edge(START, "run_pipeline")
    g.add_edge("run_pipeline", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Public entry point (mirrors pure_async_python contract for benchmark harness)
# ---------------------------------------------------------------------------

async def run_via_langgraph(
    inp: DocPipelineInput,
    llm: Optional[MockLLM] = None,
    approach: str = "vanilla",
) -> DocPipelineOutput:
    graph = build_graph(approach)
    final = await graph.ainvoke({"inp": inp, "llm": llm or MockLLM(), "approach": approach})
    return final["output"]


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _smoke() -> None:
    from pure_async_python import SAMPLE_DOCUMENT_INVOICE

    for approach in ("vanilla", "compiled"):
        inp = DocPipelineInput(
            document=SAMPLE_DOCUMENT_INVOICE,
            doc_type_hint="invoice",
            approach=approach,
        )
        out = await run_via_langgraph(inp, approach=approach)
        print(
            f"LangGraph {approach:8s}: {out.total_tokens:5d} tokens "
            f"({out.llm_calls} LLM calls) in {out.elapsed_ms:.1f} ms"
        )


if __name__ == "__main__":
    asyncio.run(_smoke())
