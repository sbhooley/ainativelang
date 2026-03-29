import argparse
import gc
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.main import cmd_golden, cmd_run
from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine


def test_compiler_emits_ir_version_and_runtime_policy():
    ir = AICodeCompiler().compile("L1: J null\n")
    assert "ir_version" in ir
    assert "runtime_policy" in ir
    assert ir["runtime_policy"]["execution_mode"] == "graph-preferred"


def test_runtime_rejects_unsupported_ir_major():
    ir = {
        "ir_version": "2.0.0",
        "labels": {"1": {"legacy": {"steps": [{"op": "J", "var": "x"}]}}},
        "source": {"lines": []},
        "cst": {"lines": []},
    }
    try:
        RuntimeEngine(ir=ir)
        assert False, "expected unsupported ir version error"
    except Exception as e:
        assert "unsupported ir_version" in str(e)


def test_runtime_unknown_op_policy_error_steps_mode():
    ir = {
        "ir_version": "1.0.0",
        "labels": {"1": {"legacy": {"steps": [{"op": "Mystery"}, {"op": "J", "var": "x"}]}}},
        "source": {"lines": []},
        "cst": {"lines": []},
    }
    eng = RuntimeEngine(ir=ir, execution_mode="steps-only", unknown_op_policy="error")
    try:
        eng.run_label("1", {"x": 1})
        assert False, "expected unknown op error"
    except Exception as e:
        assert "unknown op" in str(e)


def test_runtime_trace_sink_receives_events():
    events = []
    payload = RuntimeEngine.run("L1: Set x 1 J x\n", frame={}, trace=True, trace_sink=lambda ev: events.append(ev))
    assert payload["result"] == 1
    assert len(events) >= 2
    assert all("lineno" in e for e in events)


def test_runtime_engine_run_wrapper():
    payload = RuntimeEngine.run("L1: X x add 2 3 J x\n", frame={})
    assert payload["ok"] is True
    assert payload["runtime_version"]
    assert payload["result"] == 5


def test_cli_golden_examples_pass():
    args = argparse.Namespace(
        examples_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"),
        trace=False,
        execution_mode="graph-preferred",
        unknown_op_policy=None,
        max_steps=None,
    )
    rc = cmd_golden(args)
    assert rc == 0


def test_cli_record_and_replay_adapters_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        code_path = os.path.join(td, "prog.ainl")
        rec_path = os.path.join(td, "calls.json")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write("L1: R core.add 2 3 ->x J x\n")

        run_args = argparse.Namespace(
            self_test_graph=False,
            file=code_path,
            label="",
            strict=True,
            trace=False,
            json=True,
            no_step_fallback=False,
            execution_mode="graph-preferred",
            unknown_op_policy=None,
            trace_out="",
            record_adapters=rec_path,
            replay_adapters="",
            enable_adapter=[],
            http_allow_host=[],
            http_timeout_s=5.0,
            http_max_response_bytes=1_000_000,
            sqlite_db="",
            sqlite_allow_write=False,
            sqlite_allow_table=[],
            sqlite_timeout_s=5.0,
            fs_root="",
            fs_max_read_bytes=1_000_000,
            fs_max_write_bytes=1_000_000,
            fs_allow_ext=[],
            fs_allow_delete=False,
            tools_allow=[],
            max_steps=None,
            max_depth=None,
            max_adapter_calls=None,
            max_time_ms=None,
            max_frame_bytes=None,
            max_loop_iters=None,
        )
        assert cmd_run(run_args) == 0
        data = json.loads(open(rec_path, "r", encoding="utf-8").read())
        assert isinstance(data, list) and len(data) >= 1

        replay_args = argparse.Namespace(**{**run_args.__dict__, "record_adapters": "", "replay_adapters": rec_path})
        assert cmd_run(replay_args) == 0


def test_cli_can_enable_fs_and_sqlite_adapters():
    with tempfile.TemporaryDirectory() as td:
        code_path = os.path.join(td, "prog.ainl")
        db_path = os.path.join(td, "t.db")
        fs_root = os.path.join(td, "sandbox")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(
                "L1: R sqlite.execute \"CREATE TABLE notes (id INTEGER PRIMARY KEY, txt TEXT)\" ->a\n"
                "R sqlite.execute \"INSERT INTO notes(txt) VALUES ('hi')\" ->b\n"
                "R fs.write note.txt hi ->c\n"
                "R fs.read note.txt ->d\n"
                "J d\n"
            )
        args = argparse.Namespace(
            self_test_graph=False,
            file=code_path,
            label="",
            strict=True,
            trace=False,
            json=True,
            no_step_fallback=False,
            execution_mode="steps-only",
            unknown_op_policy="error",
            trace_out="",
            record_adapters="",
            replay_adapters="",
            enable_adapter=["sqlite", "fs"],
            http_allow_host=[],
            http_timeout_s=5.0,
            http_max_response_bytes=1_000_000,
            sqlite_db=db_path,
            sqlite_allow_write=True,
            sqlite_allow_table=["notes"],
            sqlite_timeout_s=5.0,
            fs_root=fs_root,
            fs_max_read_bytes=1_000_000,
            fs_max_write_bytes=1_000_000,
            fs_allow_ext=[],
            fs_allow_delete=False,
            tools_allow=[],
            max_steps=None,
            max_depth=None,
            max_adapter_calls=None,
            max_time_ms=None,
            max_frame_bytes=None,
            max_loop_iters=None,
        )
        # This is a smoke-path test for CLI adapter wiring; command should execute successfully.
        assert cmd_run(args) == 0
        gc.collect()
