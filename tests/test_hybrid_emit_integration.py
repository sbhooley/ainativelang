"""Hybrid emitter smoke tests: generated Python always AST-parses; Temporal import is optional."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _compile_hello_ir():
    from compiler_v2 import AICodeCompiler

    src = (ROOT / "examples/hello.ainl").read_text(encoding="utf-8")
    return AICodeCompiler(strict_mode=True).compile(src)


def test_emit_langgraph_source_parses_as_python():
    from scripts.emit_langgraph import emit_langgraph_source

    ir = _compile_hello_ir()
    text = emit_langgraph_source(ir, source_stem="hello")
    ast.parse(text)


def test_emit_temporal_pair_writes_parseable_modules(tmp_path: Path):
    from scripts.emit_temporal import emit_temporal_pair

    ir = _compile_hello_ir()
    act, wf = emit_temporal_pair(ir, output_dir=tmp_path, source_stem="hello")
    ast.parse(act.read_text(encoding="utf-8"))
    ast.parse(wf.read_text(encoding="utf-8"))


@pytest.mark.skipif(
    importlib.util.find_spec("temporalio") is None,
    reason="temporalio not installed (pip install -e '.[interop]' or '.[benchmark]')",
)
def test_temporal_activity_module_importable(tmp_path: Path):
    from scripts.emit_temporal import emit_temporal_pair

    ir = _compile_hello_ir()
    act, _wf = emit_temporal_pair(ir, output_dir=tmp_path, source_stem="hello")
    # Import emitted module by path (repo root on path for runtime.wrappers).
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("ainl_temporal_act_test", act)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    assert callable(getattr(mod, "run_ainl_core_activity_impl", None))


@pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="langgraph not installed (pip install -e '.[interop]' or '.[benchmark]')",
)
def test_langgraph_emitted_module_build_graph_invoke_e2e(tmp_path: Path):
    from scripts.emit_langgraph import emit_langgraph_source

    ir = _compile_hello_ir()
    py = tmp_path / "hello_lg_e2e.py"
    py.write_text(emit_langgraph_source(ir, source_stem="hello_e2e"), encoding="utf-8")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("hello_lg_e2e_mod", py)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    app = mod.build_graph()
    final = app.invoke({"ainl_frame": {}})
    run = final.get("ainl_run") or {}
    assert run.get("ok") is True
    assert run.get("result") == 5


@pytest.mark.skipif(
    importlib.util.find_spec("temporalio") is None,
    reason="temporalio not installed (pip install -e '.[interop]' or '.[benchmark]')",
)
def test_temporal_activity_environment_runs_emitted_impl(tmp_path: Path):
    from temporalio.testing import ActivityEnvironment

    from scripts.emit_temporal import emit_temporal_pair

    ir = _compile_hello_ir()
    act, _wf = emit_temporal_pair(ir, output_dir=tmp_path, source_stem="hello_act")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("ainl_temporal_act_e2e", act)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    env = ActivityEnvironment()
    out = env.run(mod.run_ainl_core_activity_impl, {})
    assert out.get("ok") is True
    assert out.get("result") == 5
