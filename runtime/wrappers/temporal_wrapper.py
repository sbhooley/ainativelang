"""
Execute embedded AINL IR or source inside a Temporal activity (or any durable worker).

Mirrors :func:`runtime.wrappers.langgraph_wrapper.run_ainl_graph` but uses an
``input_data`` frame dict and defaults ``strict=True`` for the from-source compile path.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine

AinlInput = Union[str, Dict[str, Any]]


def execute_ainl_activity(
    ainl_source_or_ir: AinlInput,
    input_data: Dict[str, Any],
    label: Optional[str] = None,
    *,
    adapters: Optional[AdapterRegistry] = None,
    strict: bool = True,
    strict_reachability: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Run AINL once and return an activity-friendly envelope.

    :param ainl_source_or_ir: Canonical IR dict, JSON object string, or ``.ainl`` source text.
    :param input_data: Initial frame variables for the entry label (Temporal payload).
    :param label: Optional label id; default is :meth:`RuntimeEngine.default_entry_label`.
    :param adapters: Optional :class:`AdapterRegistry`.
    :param strict: When compiling from source, passed as ``strict_mode`` / reachability.
    :param strict_reachability: If ``None``, follows ``strict``.

    Returns ``{"ok": bool, "result": ..., "error": str | None}``.
    """
    frame: Dict[str, Any] = dict(input_data or {})
    sr = strict if strict_reachability is None else strict_reachability
    try:
        if isinstance(ainl_source_or_ir, dict):
            eng = RuntimeEngine(
                ir=ainl_source_or_ir,
                adapters=adapters,
                trace=False,
                step_fallback=True,
                execution_mode="graph-preferred",
            )
        else:
            raw = str(ainl_source_or_ir).strip()
            if raw.startswith("{"):
                ir_dict: Dict[str, Any] = json.loads(raw)
                eng = RuntimeEngine(
                    ir=ir_dict,
                    adapters=adapters,
                    trace=False,
                    step_fallback=True,
                    execution_mode="graph-preferred",
                )
            else:
                eng = RuntimeEngine.from_code(
                    raw,
                    strict=strict,
                    strict_reachability=sr,
                    adapters=adapters,
                    step_fallback=True,
                    execution_mode="graph-preferred",
                )
        lid = label if label is not None else eng.default_entry_label()
        result = eng.run_label(str(lid), frame=frame)
        return {"ok": True, "result": result, "error": None}
    except Exception as e:
        return {"ok": False, "result": None, "error": str(e)}
