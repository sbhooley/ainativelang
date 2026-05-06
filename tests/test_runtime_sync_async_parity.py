"""Sync vs async runtime parity tests.

The runtime exposes both sync (``run_label`` / ``_run_label_graph``) and
async (``run_label_async`` / ``_run_label_graph_async``) execution paths
over the same IR. The audit (sbhooley/ainativelang#40 finding 5)
flagged four points where these had drifted:

1. Sync sets ``frame['_run_id']`` when starting a run; async did not.
2. Sync ``Loop`` op enforces ``max_loop_iters`` on list length; async did
   not (steps and graph variants).
3. Sync ``While`` op clamps the per-step limit by ``max_loop_iters``;
   async did not (steps and graph variants).
4. Sync graph execution has a 100000-step guard; async graph did not.

These tests pin all four behaviors as parity guarantees so future
changes touching either interpreter can't drift one half away from the
other.

Refs: sbhooley/ainativelang#40 finding 5; sbhooley/ainativelang#39 P1-7
(runtime split scaffolding -- the parity guarantee these tests pin is a
precondition for safely separating ``runtime/engine.py`` into
``runtime/graph_engine.py`` + ``runtime/error_handler.py``).
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
from typing import Any, Dict, Optional

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import RuntimeEngine


# Fixtures borrowed from tests/test_runtime_parity.py (step-vs-graph
# parity) -- known-good source that already exercises R / If / Call /
# Loop without depending on adapter availability.
PARITY_FIXTURES = [
    {
        "name": "add_and_return",
        "code": "L1: R core.add 2 3 ->x J x\n",
        "label": "1",
    },
    {
        "name": "if_then_call",
        "code": (
            "L1: Set cond true If cond ->L2 ->L3\n"
            "L2: Call L9 ->ans J ans\n"
            "L3: Set bad nope J bad\n"
            "L9: X v add 20 22 J v\n"
        ),
        "label": "1",
    },
    {
        "name": "loop_sum",
        "code": (
            "L1: X arr arr 1 2 3 Set sum 0 Loop arr item ->L2 ->L3\n"
            "L2: X sum add sum item J sum\n"
            "L3: J sum\n"
        ),
        "label": "1",
    },
    {
        "name": "call_shared_frame_mutation",
        "code": "L1: Set x 0 Call L2 J x\nL2: Set x 9 J null\n",
        "label": "1",
    },
]


def _run_sync(code: str, *, label: Optional[str] = None, frame: Optional[Dict[str, Any]] = None,
              limits: Optional[Dict[str, Any]] = None, step_fallback: bool = True) -> Any:
    eng = RuntimeEngine.from_code(code, strict=False, trace=False, step_fallback=step_fallback, limits=limits)
    lid = label or eng.default_entry_label()
    return eng.run_label(lid, frame=dict(frame or {}))


def _run_async(code: str, *, label: Optional[str] = None, frame: Optional[Dict[str, Any]] = None,
               limits: Optional[Dict[str, Any]] = None, step_fallback: bool = True) -> Any:
    eng = RuntimeEngine.from_code(code, strict=False, trace=False, step_fallback=step_fallback, limits=limits)
    lid = label or eng.default_entry_label()
    return asyncio.run(eng.run_label_async(lid, frame=dict(frame or {})))


# --- result parity across fixture set ------------------------------------


@pytest.mark.parametrize("fx", PARITY_FIXTURES, ids=lambda f: f["name"])
def test_sync_async_result_parity(fx):
    """Same IR + same frame should produce identical return values across
    both interpreters, for both step and graph execution modes."""
    sync_step = _run_sync(fx["code"], label=fx["label"], step_fallback=True)
    async_step = _run_async(fx["code"], label=fx["label"], step_fallback=True)
    assert sync_step == async_step, f"{fx['name']} step-mode mismatch: sync={sync_step!r} async={async_step!r}"

    sync_graph = _run_sync(fx["code"], label=fx["label"], step_fallback=False)
    async_graph = _run_async(fx["code"], label=fx["label"], step_fallback=False)
    assert sync_graph == async_graph, f"{fx['name']} graph-mode mismatch: sync={sync_graph!r} async={async_graph!r}"


# --- finding #40-5 specific drift pins -----------------------------------


def test_run_id_set_in_frame_after_sync_and_async_runs():
    """Drift pin: ``_run_id`` must appear in the frame after both runs.

    Sync ``_run_label`` set ``frame['_run_id']`` at the start-of-run
    branch (``not stack``); async ``_run_label_async`` only called
    ``_start_run()`` without setting the frame key. The audit's
    observation was at the internal-method level (the public
    ``run_label`` copies the frame on entry, so the mutation is not
    visible there); pin against the internal seam to match."""
    code = "L1: R core.add 1 2 ->x J x\n"

    eng_sync = RuntimeEngine.from_code(code, strict=False, trace=False)
    sync_frame: Dict[str, Any] = {}
    eng_sync._run_label("1", sync_frame, [], force_steps=False)

    eng_async = RuntimeEngine.from_code(code, strict=False, trace=False)
    async_frame: Dict[str, Any] = {}
    asyncio.run(eng_async._run_label_async("1", async_frame, [], force_steps=False))

    assert "_run_id" in sync_frame, (
        "sync _run_label must set frame['_run_id'] on stack entry"
    )
    assert "_run_id" in async_frame, (
        "async _run_label_async must set frame['_run_id'] on stack entry "
        "(audit #40-5 fix)"
    )
    # UUIDs — values themselves differ between runs.
    assert isinstance(sync_frame["_run_id"], str)
    assert isinstance(async_frame["_run_id"], str)


def test_loop_max_loop_iters_enforced_sync_and_async_steps():
    """Drift pin: in steps mode, ``Loop`` over a list must reject when
    ``len(arr) > max_loop_iters`` in BOTH sync and async."""
    code = "L1: X arr arr 1 2 3 Loop arr it ->L2 ->L3\nL2: J null\nL3: J done\n"
    limits = {"max_loop_iters": 2}
    with pytest.raises(Exception, match="max_loop_iters exceeded"):
        _run_sync(code, label="1", limits=limits, step_fallback=True)
    with pytest.raises(Exception, match="max_loop_iters exceeded"):
        _run_async(code, label="1", limits=limits, step_fallback=True)


def test_loop_max_loop_iters_enforced_sync_and_async_graph():
    """Drift pin: in graph mode, ``Loop`` over a list must reject when
    ``len(arr) > max_loop_iters`` in BOTH sync and async. This covers
    ``_run_label_graph`` and ``_run_label_graph_async`` (the graph-mode
    siblings of the steps-mode test above)."""
    code = "L1: X arr arr 1 2 3 Loop arr it ->L2 ->L3\nL2: J null\nL3: J done\n"
    limits = {"max_loop_iters": 2}
    with pytest.raises(Exception, match="max_loop_iters exceeded"):
        _run_sync(code, label="1", limits=limits, step_fallback=False)
    with pytest.raises(Exception, match="max_loop_iters exceeded"):
        _run_async(code, label="1", limits=limits, step_fallback=False)


def test_while_iteration_limit_raises_in_sync_and_async_steps():
    """Sanity parity: a runaway ``While`` must raise the same error in
    both interpreters. This pins the SHARED behavior; the
    ``max_loop_iters`` clamp specifically is pinned structurally below
    because the error string is the same regardless of which limit
    fires (per-step ``limit=`` vs runtime ``max_loop_iters``), so a
    behavioral test can't distinguish them without timing-sensitive
    assertions."""
    code = "L1: Set cond true While cond ->L2 ->L3 limit=10\nL2: J again\nL3: J done\n"
    limits = {"max_loop_iters": 2}
    with pytest.raises(Exception, match="while loop iteration limit exceeded"):
        _run_sync(code, label="1", limits=limits, step_fallback=True)
    with pytest.raises(Exception, match="while loop iteration limit exceeded"):
        _run_async(code, label="1", limits=limits, step_fallback=True)


def test_async_runtime_while_clamps_by_max_loop_iters_like_sync():
    """Drift pin: both sync and async ``While`` handlers must consult
    ``max_loop_iters`` so the per-step ``limit=`` declared in source
    can be reduced by the runtime cap.

    Behavioral test would have to distinguish which of two equal-error
    limits fired (per-step vs runtime cap) -- timing-sensitive and
    flaky. Structural pin: each interpreter that handles ``While`` must
    both reference ``max_loop_iters`` AND apply it via ``min(limit,
    max_loop_iters)`` so a future change can't silently drop the clamp
    while keeping the substring in scope."""
    sync_steps_src = inspect.getsource(RuntimeEngine._run_label)
    sync_graph_src = inspect.getsource(RuntimeEngine._run_label_graph)
    async_steps_src = inspect.getsource(RuntimeEngine._run_label_async)
    async_graph_src = inspect.getsource(RuntimeEngine._run_label_graph_async)
    for name, src in (
        ("_run_label (sync steps)", sync_steps_src),
        ("_run_label_graph (sync graph)", sync_graph_src),
        ("_run_label_async (async steps)", async_steps_src),
        ("_run_label_graph_async (async graph)", async_graph_src),
    ):
        assert "max_loop_iters" in src, (
            f"{name}: must reference max_loop_iters in While handling"
        )
        assert "min(limit, max_loop_iters)" in src, (
            f"{name}: must clamp via min(limit, max_loop_iters) in While handling "
            "(substring presence alone is not enough -- must apply the clamp)"
        )


def test_max_loop_iters_error_code_preserved_in_async_steps():
    """Drift pin: when async hits ``max_loop_iters``, the raised
    ``AinlRuntimeError`` must keep its ``RUNTIME_MAX_LOOP_ITERS`` code.

    Without a dedicated ``except AinlRuntimeError: raise`` clause in
    ``_run_label_async``, the broad ``except Exception`` rewraps the
    AinlRuntimeError via ``_raise_runtime_error`` which assigns
    ``RUNTIME_OP_ERROR``. Sync preserves the code via its own
    ``except AinlRuntimeError`` handler at L2297 -- async must match
    so the agent/MCP error contract stays consistent across paths.

    Discovered by Codex review on PR #45."""
    from runtime.engine import AinlRuntimeError, ERROR_CODE_MAX_LOOP_ITERS

    code = "L1: X arr arr 1 2 3 Loop arr it ->L2 ->L3\nL2: J null\nL3: J done\n"
    limits = {"max_loop_iters": 2}

    eng_sync = RuntimeEngine.from_code(code, strict=False, limits=limits)
    sync_err: Any = None
    try:
        eng_sync.run_label("1", frame={})
    except AinlRuntimeError as e:
        sync_err = e
    assert sync_err is not None
    assert sync_err.to_dict().get("code") == ERROR_CODE_MAX_LOOP_ITERS, (
        f"sync error code: {sync_err.to_dict().get('code')!r}"
    )

    eng_async = RuntimeEngine.from_code(code, strict=False, limits=limits)
    async_err: Any = None
    try:
        asyncio.run(eng_async.run_label_async("1", frame={}))
    except AinlRuntimeError as e:
        async_err = e
    assert async_err is not None
    assert async_err.to_dict().get("code") == ERROR_CODE_MAX_LOOP_ITERS, (
        f"async error code: {async_err.to_dict().get('code')!r} "
        "(Codex review #45 fix: must not be rewrapped to RUNTIME_OP_ERROR)"
    )


def test_async_graph_raises_on_guard_exceedance_like_sync():
    """Drift pin: both ``_run_label_graph`` and ``_run_label_graph_async``
    must reference ``ERROR_CODE_GRAPH_EXEC_GUARD`` so a runaway graph
    can't loop unbounded.

    Behavioral test would require a 100000+ step graph (impractical to
    construct from AINL source). Instead this is a structural pin: the
    error-code constant must appear in both implementations' source. A
    future change that removes the guard from either side fails here."""
    sync_src = inspect.getsource(RuntimeEngine._run_label_graph)
    async_src = inspect.getsource(RuntimeEngine._run_label_graph_async)
    assert "ERROR_CODE_GRAPH_EXEC_GUARD" in sync_src, (
        "sync graph must raise on guard exceedance (was already correct on main)"
    )
    assert "ERROR_CODE_GRAPH_EXEC_GUARD" in async_src, (
        "async graph must raise on guard exceedance (audit #40-5 fix)"
    )
