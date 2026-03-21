#!/usr/bin/env python3
"""
Handwritten baseline combining:

- ``examples/retry_error_resilience.ainl`` — ``R ext.OP "unstable_task"`` with ``Retry @n1 2 0``:
  up to **2** retries after the first failure (3 attempts total). On exhaustion, result is
  ``failed_after_retries`` (AINL ``L_fail``).
- ``modules/common/timeout.ainl`` — ``LENTRY`` uses ``R core.SLEEP 1`` (1 ms in the core adapter)
  before calling into ``WORK``. Here that is modeled as ``asyncio.sleep(0.001)`` before the retry
  loop, then the whole unit is wrapped in ``asyncio.wait_for`` for an overall deadline
  (``LEXIT_TIMEOUT``-style ``timeout`` string).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetryTimeoutConfig:
    """Tuning knobs for benchmark scenarios."""

    max_retries: int = 2
    backoff_s: float = 0.0
    deadline_s: float = 30.0
    fails_before_success: int = 2
    entry_sleep_s: float = 0.001


async def unstable_task(attempt: int, cfg: RetryTimeoutConfig) -> str:
    """
    Stand-in for ``ext.OP "unstable_task"``. Fails until ``attempt >= fails_before_success``.
    """
    await asyncio.sleep(0)
    if attempt < cfg.fails_before_success:
        raise RuntimeError("unstable_task")
    return "resp"


async def run_retry_timeout_wrapper(cfg: Optional[RetryTimeoutConfig] = None) -> str:
    """
    Returns:

    - Operation result string on success (AINL: ``J resp``),
    - ``failed_after_retries`` after ``max_retries`` is exhausted,
    - ``timeout`` if ``asyncio.wait_for`` fires (AINL timeout module ``LEXIT_TIMEOUT``).
    """
    cfg = cfg or RetryTimeoutConfig()

    async def entry_and_work() -> str:
        await asyncio.sleep(cfg.entry_sleep_s)
        for attempt in range(cfg.max_retries + 1):
            try:
                return await unstable_task(attempt, cfg)
            except RuntimeError:
                if attempt >= cfg.max_retries:
                    return "failed_after_retries"
                await asyncio.sleep(cfg.backoff_s)
        return "failed_after_retries"

    try:
        return await asyncio.wait_for(entry_and_work(), timeout=cfg.deadline_s)
    except asyncio.TimeoutError:
        return "timeout"


async def _demo() -> None:
    ok = await run_retry_timeout_wrapper(RetryTimeoutConfig())
    print("default:", ok)
    fail = await run_retry_timeout_wrapper(
        RetryTimeoutConfig(max_retries=2, fails_before_success=10, deadline_s=5.0)
    )
    print("always fail:", fail)
    tout = await run_retry_timeout_wrapper(
        RetryTimeoutConfig(
            max_retries=5,
            fails_before_success=10,
            deadline_s=0.05,
            backoff_s=0.02,
        )
    )
    print("timeout:", tout)


if __name__ == "__main__":
    asyncio.run(_demo())
