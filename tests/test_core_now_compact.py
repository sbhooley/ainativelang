"""Regression: zero-arg ``core.NOW`` in compact and ``R core.NOW ->var`` opcode forms."""
from __future__ import annotations

import pytest

from compiler_v2 import AICodeCompiler
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.engine import RuntimeEngine

pytestmark = pytest.mark.usefixtures("offline_llm_provider_config")


def _request_steps(ir: dict) -> list[dict]:
    steps: list[dict] = []
    graphs = {}
    graphs.update(ir.get("graph") or {})
    graphs.update(ir.get("labels") or {})
    for node in graphs.values():
        if not isinstance(node, dict):
            continue
        legacy = node.get("legacy") or {}
        legacy_steps = legacy.get("steps") or []
        if legacy_steps:
            for step in legacy_steps:
                if step.get("op") in ("R", "Request"):
                    steps.append(step)
            continue
        for step in node.get("nodes") or []:
            data = step.get("data") or {}
            if data.get("op") in ("R", "Request"):
                steps.append(data)
    return steps


@pytest.mark.parametrize(
    "source",
    [
        "now_compact:\n  now = core.NOW\n  out now\n",
        "now_r:\n  R core.NOW ->now\n  out now\n",
    ],
)
def test_core_now_compiles_strict(source: str):
    compiler = AICodeCompiler(strict_mode=True)
    ir = compiler.compile(source)
    assert ir.get("errors") == [], ir.get("errors")
    reqs = _request_steps(ir)
    assert len(reqs) == 1
    assert reqs[0].get("adapter") == "core.NOW"
    assert reqs[0].get("req_op") == "NOW"
    assert reqs[0].get("args") == []


def test_core_now_runtime_roundtrip():
    core = CoreBuiltinAdapter()
    value = core.call("now", [], {})
    assert isinstance(value, (int, float))
    assert value > 0

    result = RuntimeEngine.run("now_run:\n  ts = core.NOW\n  out ts\n")
    assert result.get("ok") is True or result.get("_out") is not None
