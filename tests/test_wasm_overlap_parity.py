"""Parity: metrics.wasm overlap_score_f32 vs Python overlap formula (VectorMemory-style)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

pytest.importorskip("wasmtime", reason="wasmtime not installed")

from runtime.adapters.wasm import WasmAdapter


def _py_overlap(q: float, d: float, inter: float) -> float:
    return float(inter) / (math.sqrt(q * d) + 1e-9)


def test_overlap_score_f32_parity() -> None:
    root = Path(__file__).resolve().parents[1]
    wat = root / "demo" / "wasm" / "metrics.wat"
    if not wat.is_file():
        pytest.skip("demo/wasm/metrics.wat missing")
    w = WasmAdapter(modules={"metrics": str(wat)})
    ctx: dict = {}
    for q, d, inter in [(9.0, 16.0, 6.0), (1.0, 1.0, 1.0), (100.0, 100.0, 50.0)]:
        got = w.call("CALL", ["metrics", "overlap_score_f32", q, d, inter], ctx)
        exp = _py_overlap(q, d, inter)
        assert abs(float(got) - exp) < 1e-5, (got, exp, q, d, inter)
