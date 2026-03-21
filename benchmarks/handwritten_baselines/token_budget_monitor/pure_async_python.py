#!/usr/bin/env python3
"""
Handwritten async baseline mirroring the control flow of ``openclaw/bridge/wrappers/token_budget_alert.ainl``.

Bridge and memory adapters are mocked as an in-memory ``BudgetContext`` so the benchmark is
hermetic. Thresholds (10 / 12 / 15 MB) and branch order match the AINL program.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BudgetContext:
    """In-memory stand-in for bridge + openclaw_memory side effects."""

    memory_appends: List[str] = field(default_factory=list)
    notify_adds: List[str] = field(default_factory=list)
    queue_puts: List[Tuple[str, str]] = field(default_factory=list)
    report_sent_today: bool = False

    async def token_budget_notify_reset(self) -> None:
        await asyncio.sleep(0)

    async def monitor_cache_stat(self, cache_mb: float) -> float:
        await asyncio.sleep(0)
        return cache_mb

    async def openclaw_memory_append_today(self, text: str) -> None:
        await asyncio.sleep(0)
        self.memory_appends.append(text)

    async def token_budget_warn(self, flag: int) -> bool:
        await asyncio.sleep(0)
        return bool(flag)

    async def token_budget_report(self, flag: int) -> str:
        await asyncio.sleep(0)
        _ = flag
        return "Daily AINL Status — synthetic report"

    async def token_report_today_sent(self) -> bool:
        await asyncio.sleep(0)
        return self.report_sent_today

    async def token_report_today_touch(self) -> None:
        await asyncio.sleep(0)
        self.report_sent_today = True

    async def monitor_cache_prune(self, mode: str) -> Dict[str, Any]:
        await asyncio.sleep(0)
        _ = mode
        return {"pruned_count": 1, "error": None}

    async def monitor_cache_prune_error_markdown(self) -> str:
        await asyncio.sleep(0)
        return "## Prune failed (mock)"

    async def monitor_cache_prune_markdown(self) -> str:
        await asyncio.sleep(0)
        return "## Prune ok (mock)"

    async def monitor_cache_prune_notify_text(self) -> str:
        await asyncio.sleep(0)
        return "Cache pruned (notify)"

    async def token_budget_notify_add(self, msg: str) -> None:
        await asyncio.sleep(0)
        self.notify_adds.append(msg)

    async def token_budget_notify_text(self, flag: int) -> str:
        await asyncio.sleep(0)
        _ = flag
        return "Budget notify text"

    async def token_budget_notify_build(self, ts: int) -> str:
        await asyncio.sleep(0)
        return f"Consolidated digest @ {ts}"

    async def queue_put(self, kind: str, body: str) -> None:
        await asyncio.sleep(0)
        self.queue_puts.append((kind, body))


@dataclass
class TokenBudgetInput:
    """Inputs that replace env-driven bridge behavior for a single run."""

    dry_run: bool
    cache_mb: float
    report_already_sent_today: bool
    prune_error: bool = False


@dataclass
class TokenBudgetOutput:
    report: str
    memory_appends: List[str]
    notify_adds: List[str]
    queue_puts: List[Tuple[str, str]]


def _gt(a: float, b: float) -> bool:
    return a > b


async def run_token_budget_monitor(inp: TokenBudgetInput, ctx: Optional[BudgetContext] = None) -> TokenBudgetOutput:
    """
    Execute the same branch structure as ``L_run`` … ``L_done`` in token_budget_alert.ainl.

    ``inp.cache_mb`` is injected into the mock stat call (AINL: ``R bridge monitor_cache_stat``).
    """
    ctx = ctx or BudgetContext(report_sent_today=inp.report_already_sent_today)

    await ctx.token_budget_notify_reset()
    cache_mb = await ctx.monitor_cache_stat(inp.cache_mb)

    cache_ok = 1
    report = ""
    wb = False

    # L_cache_big vs L_cache_ok_entry
    if _gt(cache_mb, 10):
        bad_note = f"- token_budget_alert: MONITOR_CACHE_JSON ~{cache_mb} MB (>10MB threshold)"
        cache_ok = 0
        await ctx.openclaw_memory_append_today(bad_note)
        if _gt(cache_mb, 15):
            if inp.dry_run:
                pass
            else:
                await ctx.token_budget_notify_add("Cache critically large — consider manual prune")
    else:
        cache_ok = 1

    # L_digest
    wb = await ctx.token_budget_warn(1)
    report = await ctx.token_budget_report(1)

    if inp.dry_run:
        pass
    else:
        dup = await ctx.token_report_today_sent()
        if not dup:
            await ctx.openclaw_memory_append_today(report)
            await ctx.token_report_today_touch()

    # L_do_prune / prune_ok / prune_failed
    if _gt(cache_mb, 12):
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
            did_prune = _gt(float(pc_int), 0)
            if did_prune and not inp.dry_run:
                pmsg = await ctx.monitor_cache_prune_notify_text()
                await ctx.token_budget_notify_add(pmsg)

    # L_done → L_finalize_notify
    if wb and cache_ok:
        pass  # L_queue_gate in AINL calls L_done → noop extra path; consolidated below

    if not inp.dry_run:
        do_budget = bool(wb) and bool(cache_ok)
        if do_budget:
            ntxt = await ctx.token_budget_notify_text(1)
            await ctx.token_budget_notify_add(ntxt)

        nts = int(time.time())
        daily = await ctx.token_budget_notify_build(nts)
        if daily:
            await ctx.queue_put("notify", daily)

    return TokenBudgetOutput(
        report=report,
        memory_appends=list(ctx.memory_appends),
        notify_adds=list(ctx.notify_adds),
        queue_puts=list(ctx.queue_puts),
    )


async def _demo() -> None:
    out = await run_token_budget_monitor(
        TokenBudgetInput(dry_run=False, cache_mb=14.0, report_already_sent_today=False, prune_error=False)
    )
    print("report:", out.report[:80], "...")
    print("memory lines:", len(out.memory_appends))
    print("queue:", out.queue_puts)


if __name__ == "__main__":
    asyncio.run(_demo())
