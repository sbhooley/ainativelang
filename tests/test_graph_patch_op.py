# pylint: disable=missing-module-docstring
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_diagnostics import StrictModeError
from compiler_v2 import AICodeCompiler


def _isolated_bridge(tmp_path):
    from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge, GraphStore

    p = tmp_path / "graph_mem.json"
    p.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    store = GraphStore(path=p)
    return AINLGraphMemoryBridge(store=store)


def _ir_with_agent(ir: dict, agent_id: str) -> dict:
    ir = dict(ir)
    services = dict(ir.get("services") or {})
    core = dict(services.get("core") or {})
    core["agent_id"] = agent_id
    services["core"] = core
    ir["services"] = services
    return ir


def test_patch_and_call_step_mode(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "step_pat",
        [
            {"op": "Set", "name": "outv", "ref": "step_ok", "__literal_fields": {"ref": True}},
            {"op": "J", "var": "outv"},
        ],
        "agent_step",
        [],
    )
    code = """S app core noop
L1:
  R memory.patch "step_pat" "dyn_lbl" ->patch_res
  Call dyn_lbl
  J _call_result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_step")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {"agent_id": "agent_step"})
    assert out == "step_ok"


def test_patch_and_call_graph_mode(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "graph_pat",
        [
            {"op": "Set", "name": "gv", "ref": 77},
            {"op": "J", "var": "gv"},
        ],
        "agent_graph",
        [],
    )
    code = """S app core noop
L1:
  R memory.patch "graph_pat" "gpatch_lbl" ->_
  Call gpatch_lbl
  J _call_result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_graph")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="graph-preferred")
    out = eng.run_label("1", {"agent_id": "agent_graph"})
    assert out == 77


def test_patch_by_frame_variable(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "frame_pat_a",
        [
            {"op": "Set", "name": "msg", "ref": "from_frame", "__literal_fields": {"ref": True}},
            {"op": "J", "var": "msg"},
        ],
        "agent_frame",
        [],
    )
    code = """S app core noop
L1:
  Set pname "frame_pat_a"
  R memory.patch $pname "frame_lbl" ->_
  Call frame_lbl
  J _call_result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_frame")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {"agent_id": "agent_frame"})
    assert out == "from_frame"


def test_overwrite_guard(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import AinlRuntimeError, RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "ow_pat",
        [{"op": "Set", "name": "z", "ref": "bad", "__literal_fields": {"ref": True}}, {"op": "J", "var": "z"}],
        "agent_ow",
        [],
    )
    code = """S app core noop
L1:
  R memory.patch "ow_pat" "2" ->_
L2:
  Set k 1
  J k
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_ow")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    with pytest.raises(AinlRuntimeError, match="GraphPatch cannot overwrite compiled label"):
        eng.run_label("1", {"agent_id": "agent_ow"})


def test_repatch_increments_version(tmp_path):
    from armaraos.bridge.ainl_graph_memory import PatchRecord

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "rp_v1",
        [{"op": "J", "var": "one"}],
        "agent_rp",
        [],
    )
    r1 = bridge.memory_patch("rp_v1", "rp_lbl", agent_id="agent_rp")
    assert r1.get("ok") and r1.get("patch_version") == 1
    bridge.memory_store_pattern(
        "rp_v2",
        [{"op": "J", "var": "two"}],
        "agent_rp",
        [],
    )
    r2 = bridge.memory_patch("rp_v2", "rp_lbl", agent_id="agent_rp")
    assert r2.get("ok") and r2.get("patch_version") == 2
    assert r2.get("parent_patch_id") == r1.get("node_id")
    cur = bridge._store.get_patch_record("rp_lbl", "agent_rp")
    assert cur is not None
    assert isinstance(cur, PatchRecord)
    assert cur.patch_version == 2
    parent = bridge._store.get_node(str(r1["node_id"]))
    assert parent is not None
    prev = PatchRecord.from_payload(parent.payload or {})
    assert prev.retired_at is not None


def test_boot_reinstallation(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "boot_pat",
        [
            {"op": "Set", "name": "boot_v", "ref": "reloaded", "__literal_fields": {"ref": True}},
            {"op": "J", "var": "boot_v"},
        ],
        "agent_boot",
        [],
    )
    code = """S app core noop
L1:
  R memory.patch "boot_pat" "boot_lbl" ->_
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_boot")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng1 = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    eng1.run_label("1", {"agent_id": "agent_boot"})

    reinstall_calls = []
    _orig_reinstall = RuntimeEngine._reinstall_patches

    def _track_reinstall(self):
        reinstall_calls.append(1)
        return _orig_reinstall(self)

    ir2 = _ir_with_agent(comp.compile(code, emit_graph=True), "agent_boot")
    reg2 = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg2.register("ainl_graph_memory", bridge)
    with mock.patch.object(RuntimeEngine, "_reinstall_patches", _track_reinstall):
        eng2 = RuntimeEngine(ir2, adapters=reg2, execution_mode="steps-only")
    assert reinstall_calls == [1]
    body = eng2.labels.get("boot_lbl") or {}
    assert body.get("__patched__") is True
    out = eng2.run_label("boot_lbl", {"agent_id": "agent_boot"})
    assert out == "reloaded"


def test_fitness_ema_update(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "fit_pat",
        [{"op": "Set", "name": "fv", "ref": 1}, {"op": "J", "var": "fv"}],
        "agent_fit",
        [],
    )
    code = """S app core noop
L1:
  R memory.patch "fit_pat" "fit_lbl" ->_
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    ir = _ir_with_agent(ir, "agent_fit")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    eng.run_label("1", {"agent_id": "agent_fit"})
    eng.run_label("fit_lbl", {"agent_id": "agent_fit"})
    body = eng.labels.get("fit_lbl") or {}
    assert abs(float(body.get("__fitness__", 0)) - 0.6) < 1e-9
    eng.run_label("fit_lbl", {"agent_id": "agent_fit"})
    body = eng.labels.get("fit_lbl") or {}
    assert abs(float(body.get("__fitness__", 0)) - 0.68) < 1e-9


def test_strict_compile():
    code = """S app core noop
L1:
  R memory.patch "lit_pat" "lit_lbl" ->pr
  J pr
"""
    with pytest.raises(StrictModeError):
        AICodeCompiler(strict_literals=True).compile(code, emit_graph=True)
