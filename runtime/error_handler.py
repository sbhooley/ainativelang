"""Runtime error handling and routing.

Extracted from ``runtime/engine.py`` to isolate the error-shaping and
graph-error-routing surface in its own module. Like
``runtime/graph_engine.py``, the functions here are attached to
``RuntimeEngine`` at the bottom of ``runtime/engine.py`` via
``setattr``, preserving the existing ``self.X(...)`` call shape.

Three pieces:

- ``_source_context`` -- look up the source line + op span for a given
  IR ``lineno``. Pure helper, used only by ``_raise_runtime_error``.
- ``_raise_runtime_error`` -- shape an arbitrary exception into an
  ``AinlRuntimeError`` with structured data (cause type, source
  context, capability-gate hint). Called from both step and graph
  interpreters.
- ``_route_graph_error`` -- inspect outgoing ``port="err"`` edges from
  the current graph node, route to the declared handler if any, and
  surface ``handled=True/False`` to the caller.

Late binding (rather than a Mixin) avoids a module-import cycle: this
module imports ``AinlRuntimeError``, ``AdapterError``, error-code
constants, and ``_norm_lid`` from ``runtime.engine``, and is itself
only imported at the bottom of ``runtime/engine.py``.

Audit ref: sbhooley/ainativelang#39 P1-7 (error handling extraction
from the broader L1478-1920 range).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.engine import (
    AdapterError,
    AinlRuntimeError,
    ERROR_CODE_ADAPTER_ERROR,
    ERROR_CODE_ERR_HANDLER_RECURSION,
    ERROR_CODE_RUNTIME_OP_ERROR,
    _norm_lid,
)


def _source_context(self, lineno: Optional[int]) -> Dict[str, Any]:
    if not lineno or lineno < 1:
        return {}
    line = self._source_lines[lineno - 1] if lineno - 1 < len(self._source_lines) else ""
    cst = self._cst_by_line.get(lineno, {})
    op_tok = None
    for t in (cst.get("tokens") or []):
        if t.get("kind") in ("bare", "string"):
            op_tok = t
            break
    return {"lineno": lineno, "line": line, "op_span": op_tok.get("span") if isinstance(op_tok, dict) else None}


def _raise_runtime_error(
    self,
    err: Exception,
    lid: str,
    idx: int,
    op: str,
    stack: List[str],
    frame: Dict[str, Any],
    step: Dict[str, Any],
    *,
    node_id: Optional[str] = None,
) -> None:
    self._emit_trajectory_fail(lid, op, frame, step, err, node_id=node_id)
    public_lid = stack[-2] if lid == "__tmp__" and len(stack) >= 2 else lid
    ctx = self._source_context(step.get("lineno"))
    msg = str(err)
    if ctx:
        msg = f"{msg} [line={ctx.get('lineno')} source={ctx.get('line')!r}]"
    data = {
        "cause_type": type(err).__name__,
        "cause_message": str(err),
        "lineno": ctx.get("lineno") if ctx else None,
        "source": ctx.get("line") if ctx else None,
    }
    code = ERROR_CODE_ADAPTER_ERROR if isinstance(err, AdapterError) else ERROR_CODE_RUNTIME_OP_ERROR
    if isinstance(err, AdapterError) and "capability gate" in str(err):
        data["user_hint"] = (
            "This step needs an adapter your host has not enabled. "
            "See the error text for AINL_HOST_ADAPTER_ALLOWLIST, AINL_HOST_ADAPTER_DENYLIST, "
            "AINL_STRICT_MODE, and AINL_SECURITY_PROFILE."
        )
    raise AinlRuntimeError(msg, public_lid, idx, op, stack, code=code, data=data)


def _route_graph_error(
    self,
    err: Exception,
    *,
    cur: Optional[str],
    out_by_from: Dict[str, List[Dict[str, Any]]],
    node_by_id: Dict[str, Dict[str, Any]],
    active_err_handler: Optional[str],
    lid: str,
    idx: int,
    op: str,
    stack: List[str],
    frame: Dict[str, Any],
) -> Dict[str, Any]:
    err_edge = next((ed for ed in out_by_from.get(cur, []) if ed.get("port") == "err"), None)
    handler: Optional[str] = None
    if err_edge and err_edge.get("to_kind") == "node":
        err_node = node_by_id.get(err_edge.get("to"))
        h_step = (err_node or {}).get("data", {})
        if h_step.get("op") == "Err":
            handler = _norm_lid(h_step.get("handler"))
    if not handler:
        handler = active_err_handler
    if not handler:
        return {"handled": False}
    if handler in stack:
        raise AinlRuntimeError(
            f"error handler recursion detected: handler={handler} failing_op={op}",
            lid,
            idx,
            op,
            stack,
            code=ERROR_CODE_ERR_HANDLER_RECURSION,
        )
    frame["_error"] = str(err)
    step_data = (node_by_id.get(cur or "") or {}).get("data")
    if not isinstance(step_data, dict):
        step_data = {"op": op}
    if self._trajectory_log_path:
        self._emit_trajectory_fail(lid, op, frame, step_data, err, node_id=cur)
    if self.trace_enabled:
        self.trace_events.append(
            {"err_routed": True, "from_node": cur, "handler": handler, "label": lid}
        )
        if self.trace_sink is not None:
            self.trace_sink(self.trace_events[-1])
    out = self._run_label(handler, frame, stack, force_steps=False)
    return {"handled": True, "out": out}
