# pylint: disable=missing-module-docstring
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler


def _isolated_bridge(tmp_path):
    from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge, GraphStore

    p = tmp_path / "graph_mem.json"
    p.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    store = GraphStore(path=p)
    return AINLGraphMemoryBridge(store=store)


def test_memory_execute_from_frame_variable(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "greet_user",
        [
            {"op": "Set", "name": "greeting", "ref": "hello"},
            {"op": "J", "var": "greeting"},
        ],
        "test_agent",
        ["greeting"],
    )
    code = """S app core noop
L1:
  R memory.pattern_recall "greet_user" ->pat
  R memory.execute $pat ->result
  J result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {"agent_id": "test_agent"})
    assert out == "hello"


def test_memory_execute_by_pattern_name(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "by_name_pat",
        [{"op": "Set", "name": "x", "ref": "99"}, {"op": "J", "var": "x"}],
        "ag2",
        [],
    )
    code = """S app core noop
L1:
  R memory.execute "by_name_pat" ->result
  J result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {"agent_id": "ag2"})
    assert out == 99


def test_memory_execute_graph_preferred(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    bridge.memory_store_pattern(
        "graph_pat",
        [{"op": "Set", "name": "n", "ref": "7"}, {"op": "J", "var": "n"}],
        "ag3",
        [],
    )
    code = """S app core noop
L1:
  R memory.pattern_recall "graph_pat" ->pat
  R memory.execute $pat ->result
  J result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="graph-preferred")
    out = eng.run_label("1", {"agent_id": "ag3"})
    assert out == 7


def test_memory_execute_missing_pattern_no_exception(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.engine import RuntimeEngine

    bridge = _isolated_bridge(tmp_path)
    code = """S app core noop
L1:
  R memory.execute "missing_pattern_xyz" ->exec_result
  J exec_result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", bridge)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {"agent_id": "solo"})
    assert isinstance(out, dict)
    assert out.get("ok") is False
    assert (out.get("steps") in (None, []))


def test_memory_execute_strict_compile():
    code = """S app core noop
L1:
  R memory.execute "my_pattern" * ->res
  J res
"""
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
