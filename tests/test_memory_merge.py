# pylint: disable=missing-module-docstring
from compiler_v2 import AICodeCompiler

TEST_PROVENANCE = AICodeCompiler()._emit_provenance_comment_block("#", "AINL pytest: test_memory_merge")


def test_memory_merge_store_then_run_returns_exit_value(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.adapters.memory import MemoryAdapter
    from runtime.engine import RuntimeEngine

    db = str(tmp_path / "mem.sqlite3")
    mem = MemoryAdapter(db_path=db)
    frag = {
        "labels": {
            "1": {
                "legacy": {
                    "steps": [
                        {"op": "Set", "lineno": 1, "name": "x", "ref": "42", "__literal_fields": {"ref": True}},
                        {"op": "J", "lineno": 2, "var": "x", "__literal_fields": {"var": True}},
                    ]
                },
                "nodes": [],
                "edges": [],
            }
        }
    }
    mem.store_pattern("greet", frag)

    code = """S app core noop
L1:
memory.merge greet ->result
J result
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    reg = AdapterRegistry()
    reg.register("memory", mem)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    out = eng.run_label("1", {})
    assert out == 42


def test_memory_merge_missing_pattern_warns_and_no_raise(tmp_path, caplog):
    import logging

    from runtime.adapters.base import AdapterRegistry
    from runtime.adapters.memory import MemoryAdapter
    from runtime.engine import RuntimeEngine

    db = str(tmp_path / "mem2.sqlite3")
    mem = MemoryAdapter(db_path=db)
    code = """S app core noop
L1:
memory.merge no_such_pattern ->r
J r
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    reg = AdapterRegistry()
    reg.register("memory", mem)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    with caplog.at_level(logging.WARNING):
        eng.run_label("1", {})
    assert any("memory.merge" in r.message for r in caplog.records)


def test_memory_merge_prefixed_labels_no_collision(tmp_path):
    from runtime.adapters.base import AdapterRegistry
    from runtime.adapters.memory import MemoryAdapter
    from runtime.engine import RuntimeEngine

    db = str(tmp_path / "mem3.sqlite3")
    mem = MemoryAdapter(db_path=db)
    inner = {
        "labels": {
            "1": {
                "legacy": {
                    "steps": [
                        {"op": "Set", "lineno": 1, "name": "x", "ref": "7", "__literal_fields": {"ref": True}},
                        {"op": "J", "lineno": 2, "var": "x", "__literal_fields": {"var": True}},
                    ]
                },
                "nodes": [],
                "edges": [],
            }
        }
    }
    mem.store_pattern("inner", inner)

    code = """S app core noop
L1:
Set y 99
memory.merge inner ->out
J y
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    reg = AdapterRegistry()
    reg.register("memory", mem)
    eng = RuntimeEngine(ir, adapters=reg, execution_mode="steps-only")
    eng.run_label("1", {})
    keys = list(eng.labels.keys())
    prefixed = [k for k in keys if k.startswith("_mm_") and k.endswith("_1")]
    assert len(prefixed) == 1
    assert eng.labels["1"]["legacy"]["steps"][0]["op"] == "Set"
