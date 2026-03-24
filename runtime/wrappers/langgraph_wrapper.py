"""
Run compiled AINL IR or source through :class:`runtime.engine.RuntimeEngine`.

Intended for LangGraph (or similar) nodes: pass orchestration state keys via ``state``;
they become the initial frame for ``run_label``. Optional ``adapters`` mirrors the CLI
host pattern (``None`` → registry built from IR ``capabilities`` plus built-in ``core``).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine

AinlInput = Union[str, Dict[str, Any]]


def run_ainl_graph(
    ainl_source_or_ir: AinlInput,
    state: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
    *,
    adapters: Optional[AdapterRegistry] = None,
    strict: bool = False,
    strict_reachability: bool = False,
) -> Dict[str, Any]:
    """
    Execute AINL once and return a LangGraph-friendly envelope.

    :param ainl_source_or_ir: Canonical IR dict, JSON object string, or ``.ainl`` source text.
    :param state: Initial frame variables (merged as the runtime frame for the entry label).
    :param label: Optional label id; default is :meth:`RuntimeEngine.default_entry_label`.
    :param adapters: Optional :class:`AdapterRegistry` (e.g. with ``--enable-adapter`` parity).
    :param strict: Passed to :meth:`RuntimeEngine.from_code` when ``ainl_source_or_ir`` is source.
    :param strict_reachability: Same as ``strict`` for from-code path.

    Returns ``{"ok": bool, "result": ..., "label": str | None, "error": str | None}``.
    """
    frame: Dict[str, Any] = dict(state or {})
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
                    strict_reachability=strict_reachability,
                    adapters=adapters,
                    step_fallback=True,
                    execution_mode="graph-preferred",
                )
        lid = label if label is not None else eng.default_entry_label()
        result = eng.run_label(str(lid), frame=frame)
        return {"ok": True, "result": result, "label": str(lid), "error": None}
    except Exception as e:
        return {"ok": False, "result": None, "label": None, "error": str(e)}
