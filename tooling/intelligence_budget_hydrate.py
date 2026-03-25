"""Merge SQLite rolling budget (weekly_remaining_v1) into cache workflow.token_budget.

Intelligence programs (`token_aware_startup_context`, `proactive_session_summarizer`) read
``R cache get "workflow" "token_budget"`` with a ``daily_remaining`` field. The bridge
publishes weekly aggregates to memory via ``rolling_budget_publish``; this module copies
those signals into the same cache key **without** overwriting richer state written by
``session_budget_enforcer`` unless the merge policy says so.

Environment:
- ``AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE``: set to ``1`` to disable.
- ``AINL_INTELLIGENCE_ROLLING_CONSERVATIVE_DAILY``: default ``1`` — if set, set
  ``daily_remaining`` to ``min(existing, weekly_remaining//7)`` when both exist.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ROLLING_NS = "workflow"
_ROLLING_KIND = "budget.aggregate"
_ROLLING_ID = "weekly_remaining_v1"


def _weekly_remaining_from_payload(payload: Dict[str, Any]) -> Optional[int]:
    raw = payload.get("weekly_remaining_tokens")
    if raw is None:
        return None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


def _conservative_daily(weekly_remaining: int) -> int:
    return max(0, weekly_remaining // 7)


def merge_token_budget_with_rolling(
    existing: Any,
    rolling_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a new dict: existing cache object merged with rolling budget fields."""
    base: Dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    wr = _weekly_remaining_from_payload(rolling_payload)
    base["rolling_weekly_remaining_tokens"] = wr
    base["rolling_avg_daily_tokens"] = rolling_payload.get("avg_daily_tokens")
    base["rolling_days_in_window"] = rolling_payload.get("days_in_window")
    base["rolling_weekly_cap_tokens"] = rolling_payload.get("weekly_cap_tokens")
    base["rolling_source"] = "memory.budget.aggregate.weekly_remaining_v1"
    base["rolling_updated_at_utc"] = rolling_payload.get("updated_at_utc")
    if wr is None:
        return base
    daily_from_rolling = _conservative_daily(wr)
    conservative = os.environ.get("AINL_INTELLIGENCE_ROLLING_CONSERVATIVE_DAILY", "1").strip() == "1"
    prev = base.get("daily_remaining")
    try:
        prev_i = int(prev) if prev is not None else None
    except (TypeError, ValueError):
        prev_i = None
    if prev_i is None:
        base["daily_remaining"] = daily_from_rolling
    elif conservative:
        base["daily_remaining"] = min(prev_i, daily_from_rolling)
    else:
        base["daily_remaining"] = daily_from_rolling
    return base


def hydrate_budget_cache_from_rolling_memory(registry: Any) -> Dict[str, Any]:
    """
    Read rolling budget from memory adapter; merge into CacheAdapter workflow/token_budget.

    ``registry`` is an ``AdapterRegistry`` with ``memory`` and ``cache`` registered.
    """
    if os.environ.get("AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE", "").strip() == "1":
        return {"ok": True, "skipped": True, "reason": "AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE"}
    ctx: Dict[str, Any] = {}
    try:
        got = registry.call("memory", "get", [_ROLLING_NS, _ROLLING_KIND, _ROLLING_ID], ctx)
    except Exception as e:
        logger.warning("hydrate: memory get failed: %s", e)
        return {"ok": False, "error": "memory_get"}
    if not isinstance(got, dict) or not got.get("found"):
        return {"ok": True, "skipped": True, "reason": "no_rolling_record"}
    rec = got.get("record") or {}
    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {"ok": True, "skipped": True, "reason": "rolling_payload_not_object"}

    try:
        existing = registry.call("cache", "get", ["workflow", "token_budget"], ctx)
    except Exception as e:
        logger.warning("hydrate: cache get failed: %s", e)
        return {"ok": False, "error": "cache_get"}
    merged = merge_token_budget_with_rolling(existing, payload)
    try:
        registry.call("cache", "set", ["workflow", "token_budget", merged], ctx)
    except Exception as e:
        logger.warning("hydrate: cache set failed: %s", e)
        return {"ok": False, "error": "cache_set"}
    return {
        "ok": True,
        "merged_keys": sorted(merged.keys()),
        "weekly_remaining_tokens": merged.get("rolling_weekly_remaining_tokens"),
        "daily_remaining": merged.get("daily_remaining"),
    }
