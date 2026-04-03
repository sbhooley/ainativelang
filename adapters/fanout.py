"""Parallel fan-out over existing adapters (thread pool).

Requires ``context["_adapter_registry"]`` (injected by :class:`runtime.engine.RuntimeEngine`).

Verbs:
  ALL — args[0] is JSON string or list of plans; each plan is
        ``[adapter, target, arg1, arg2, ...]`` (same shape as :meth:`AdapterRegistry.call`).

Env:
  AINL_FANOUT_MAX_WORKERS — default 8
  AINL_FANOUT_DISABLE — when truthy, run sequentially (debug / ordering-sensitive)
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from runtime.adapters.base import AdapterError, RuntimeAdapter


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


class FanoutAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().upper()
        if verb != "ALL":
            raise AdapterError("fanout supports ALL")
        reg = context.get("_adapter_registry")
        if reg is None:
            raise AdapterError("fanout.ALL requires runtime _adapter_registry in context")
        if not args:
            raise AdapterError("fanout.ALL requires a JSON list of [adapter, target, ...args]")
        raw = args[0]
        if isinstance(raw, str):
            plans = json.loads(raw)
        else:
            plans = raw
        if not isinstance(plans, list):
            raise AdapterError("fanout.ALL payload must be a JSON list")

        def one(p: Any) -> Any:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                raise AdapterError("each fanout plan must be [adapter, target, ...args]")
            ad = str(p[0])
            tgt = str(p[1])
            rest = list(p[2:])
            return reg.call(ad, tgt, rest, context)

        if _truthy(os.environ.get("AINL_FANOUT_DISABLE")):
            return [one(p) for p in plans]

        max_w = max(1, min(32, int(os.environ.get("AINL_FANOUT_MAX_WORKERS", "8"))))
        with ThreadPoolExecutor(max_workers=min(max_w, max(1, len(plans)))) as ex:
            return list(ex.map(one, plans))
