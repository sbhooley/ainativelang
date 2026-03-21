#!/usr/bin/env python3
"""
LangGraph-shaped version of ``token_budget_alert.ainl`` using the same ``BudgetContext`` mocks.

Nodes correspond to major AINL regions (digest, prune, finalize). Conditional routing encodes
``If c10``, ``If c12``, etc. Logic is duplicated from ``pure_async_python`` for a clear graph
mapping (kept in sync with the sequential baseline).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

_SUB = Path(__file__).resolve().parent
if str(_SUB) not in sys.path:
    sys.path.insert(0, str(_SUB))

from pure_async_python import (  # noqa: E402
    BudgetContext,
    TokenBudgetInput,
    TokenBudgetOutput,
    _gt,
    run_token_budget_monitor,
)

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "langgraph is required for this baseline. Install with: pip install langgraph"
    ) from e


class TBState(TypedDict, total=False):
    inp: TokenBudgetInput
    ctx: BudgetContext
    cache_mb: float
    cache_ok: int
    report: str
    wb: bool
    pr: Dict[str, Any]
    daily: str
    memory_appends: List[str]
    notify_adds: List[str]
    queue_puts: List[Tuple[str, str]]


async def node_reset_and_stat(state: TBState) -> Dict[str, Any]:
    inp = state["inp"]
    ctx = state["ctx"]
    await ctx.token_budget_notify_reset()
    cache_mb = await ctx.monitor_cache_stat(inp.cache_mb)
    return {"cache_mb": cache_mb}


async def node_threshold_10(state: TBState) -> Dict[str, Any]:
    inp = state["inp"]
    ctx = state["ctx"]
    cache_mb = state["cache_mb"]
    if _gt(cache_mb, 10):
        bad_note = f"- token_budget_alert: MONITOR_CACHE_JSON ~{cache_mb} MB (>10MB threshold)"
        cache_ok = 0
        await ctx.openclaw_memory_append_today(bad_note)
        if _gt(cache_mb, 15) and not inp.dry_run:
            await ctx.token_budget_notify_add("Cache critically large — consider manual prune")
    else:
        cache_ok = 1
    return {"cache_ok": cache_ok}


async def node_digest(state: TBState) -> Dict[str, Any]:
    inp = state["inp"]
    ctx = state["ctx"]
    wb = await ctx.token_budget_warn(1)
    report = await ctx.token_budget_report(1)
    if not inp.dry_run:
        dup = await ctx.token_report_today_sent()
        if not dup:
            await ctx.openclaw_memory_append_today(report)
            await ctx.token_report_today_touch()
    return {"wb": wb, "report": report}


async def node_prune(state: TBState) -> Dict[str, Any]:
    inp = state["inp"]
    ctx = state["ctx"]
    cache_mb = state["cache_mb"]
    report = state.get("report", "")
    if not _gt(cache_mb, 12):
        return {"report": report}
    pr = await ctx.monitor_cache_prune("auto")
    if inp.prune_error:
        pr = {"pruned_count": 0, "error": "forced"}
    pe = bool(pr.get("error")) if isinstance(pr, dict) else False
    if pe:
        emd = await ctx.monitor_cache_prune_error_markdown()
        await ctx.openclaw_memory_append_today(emd)
        report = f"{report}\n\n{emd}"
    else:
        prune_md = await ctx.monitor_cache_prune_markdown()
        await ctx.openclaw_memory_append_today(prune_md)
        report = f"{report}\n\n{prune_md}"
        pc_int = int(pr.get("pruned_count") or 0)
        if pc_int > 0 and not inp.dry_run:
            pmsg = await ctx.monitor_cache_prune_notify_text()
            await ctx.token_budget_notify_add(pmsg)
    return {"report": report, "pr": pr}


async def node_finalize(state: TBState) -> Dict[str, Any]:
    inp = state["inp"]
    ctx = state["ctx"]
    wb = bool(state.get("wb"))
    cache_ok = int(state.get("cache_ok", 1))
    report = state.get("report", "")
    if not inp.dry_run:
        if wb and cache_ok:
            ntxt = await ctx.token_budget_notify_text(1)
            await ctx.token_budget_notify_add(ntxt)
        nts = int(time.time())
        daily = await ctx.token_budget_notify_build(nts)
        if daily:
            await ctx.queue_put("notify", daily)
    return {
        "memory_appends": list(ctx.memory_appends),
        "notify_adds": list(ctx.notify_adds),
        "queue_puts": list(ctx.queue_puts),
        "report": report,
        "daily": state.get("daily", ""),
    }


def build_token_budget_graph():
    g = StateGraph(TBState)
    g.add_node("reset_stat", node_reset_and_stat)
    g.add_node("threshold", node_threshold_10)
    g.add_node("digest", node_digest)
    g.add_node("prune", node_prune)
    g.add_node("finalize", node_finalize)
    g.add_edge(START, "reset_stat")
    g.add_edge("reset_stat", "threshold")
    g.add_edge("threshold", "digest")
    g.add_edge("digest", "prune")
    g.add_edge("prune", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


async def run_via_langgraph(inp: TokenBudgetInput, ctx: Optional[BudgetContext] = None) -> TokenBudgetOutput:
    """Run the graph; package the same ``TokenBudgetOutput`` as the pure-async function."""
    ctx = ctx or BudgetContext(report_sent_today=inp.report_already_sent_today)
    app = build_token_budget_graph()
    final = await app.ainvoke({"inp": inp, "ctx": ctx})
    return TokenBudgetOutput(
        report=str(final.get("report", "")),
        memory_appends=list(final.get("memory_appends") or []),
        notify_adds=list(final.get("notify_adds") or []),
        queue_puts=list(final.get("queue_puts") or []),
    )


async def _verify_equivalence() -> None:
    for mb in (4.0, 11.0, 13.5, 16.0):
        for dry in (True, False):
            for dup in (True, False):
                for perr in (False, True):
                    inp = TokenBudgetInput(
                        dry_run=dry,
                        cache_mb=mb,
                        report_already_sent_today=dup,
                        prune_error=perr,
                    )
                    ctx_a = BudgetContext(report_sent_today=dup)
                    ctx_b = BudgetContext(report_sent_today=dup)
                    a = await run_token_budget_monitor(inp, ctx_a)
                    b = await run_via_langgraph(inp, ctx_b)
                    assert a.report == b.report, (mb, dry, dup, perr, a.report, b.report)
                    assert a.memory_appends == b.memory_appends
                    assert a.notify_adds == b.notify_adds
                    assert a.queue_puts == b.queue_puts
    print("equivalence check: ok")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_verify_equivalence())
