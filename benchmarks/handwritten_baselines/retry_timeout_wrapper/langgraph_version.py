#!/usr/bin/env python3
"""
LangGraph version of the retry + timeout wrapper: stand-in delay node, then a try/backoff loop
with conditional edges. Overall deadline uses ``asyncio.wait_for`` around ``graph.ainvoke``,
matching the outer timeout envelope in ``pure_async_python.run_retry_timeout_wrapper``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Literal, Optional, TypedDict

_SUB = Path(__file__).resolve().parent
if str(_SUB) not in sys.path:
    sys.path.insert(0, str(_SUB))

from pure_async_python import RetryTimeoutConfig, run_retry_timeout_wrapper, unstable_task  # noqa: E402

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError("langgraph is required. Install with: pip install langgraph") from e


class RTWState(TypedDict, total=False):
    cfg: RetryTimeoutConfig
    attempt: int
    result: str


async def node_entry_sleep(state: RTWState) -> dict:
    await asyncio.sleep(state["cfg"].entry_sleep_s)
    return {"attempt": 0}


async def node_try(state: RTWState) -> dict:
    cfg = state["cfg"]
    attempt = int(state.get("attempt", 0))
    try:
        out = await unstable_task(attempt, cfg)
        return {"result": out}
    except RuntimeError:
        if attempt >= cfg.max_retries:
            return {"result": "failed_after_retries"}
        return {"attempt": attempt + 1}


async def node_backoff(state: RTWState) -> dict:
    await asyncio.sleep(state["cfg"].backoff_s)
    return {}


def route_after_try(state: RTWState) -> Literal["done", "retry"]:
    if state.get("result"):
        return "done"
    return "retry"


def build_retry_timeout_graph():
    g = StateGraph(RTWState)
    g.add_node("entry", node_entry_sleep)
    g.add_node("try_op", node_try)
    g.add_node("backoff", node_backoff)
    g.add_edge(START, "entry")
    g.add_edge("entry", "try_op")
    g.add_conditional_edges(
        "try_op",
        route_after_try,
        {"done": END, "retry": "backoff"},
    )
    g.add_edge("backoff", "try_op")
    return g.compile()


async def run_via_langgraph(cfg: Optional[RetryTimeoutConfig] = None) -> str:
    cfg = cfg or RetryTimeoutConfig()
    app = build_retry_timeout_graph()

    async def body() -> str:
        final = await app.ainvoke({"cfg": cfg})
        return str(final.get("result", "failed_after_retries"))

    try:
        return await asyncio.wait_for(body(), timeout=cfg.deadline_s)
    except asyncio.TimeoutError:
        return "timeout"


async def _verify_equivalence() -> None:
    for fails in (0, 1, 2, 3):
        for mr in (1, 2, 3):
            cfg = RetryTimeoutConfig(max_retries=mr, fails_before_success=fails, deadline_s=10.0)
            a = await run_retry_timeout_wrapper(cfg)
            b = await run_via_langgraph(cfg)
            assert a == b, (fails, mr, a, b)
    print("equivalence check: ok")


if __name__ == "__main__":
    asyncio.run(_verify_equivalence())
