"""Tests for openclaw/bridge/ir_cache.py (wrapper compile cache)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE = _ROOT / "openclaw" / "bridge"
_spec = importlib.util.spec_from_file_location("ainl_ir_cache_test", _BRIDGE / "ir_cache.py")
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compile_source_cached = _mod.compile_source_cached
load_cached_ir = _mod.load_cached_ir
save_cached_ir = _mod.save_cached_ir


def test_ir_cache_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AINL_IR_CACHE", "1")
    monkeypatch.setenv("AINL_IR_CACHE_DIR", str(tmp_path / "cache"))

    src = tmp_path / "hello.ainl"
    src.write_text("S core cron \"0 * * * *\"\nL0:\n  J 0\n", encoding="utf-8")

    calls = {"n": 0}

    def fake_compile(text: str) -> dict:
        calls["n"] += 1
        return {"ok": True, "fake": True, "src_len": len(text)}

    ir1 = compile_source_cached(src, fake_compile)
    assert ir1["ok"] is True
    assert calls["n"] == 1

    ir2 = compile_source_cached(src, fake_compile)
    assert ir2 == ir1
    assert calls["n"] == 1

    src.write_text(src.read_text() + "\n", encoding="utf-8")
    ir3 = compile_source_cached(src, fake_compile)
    assert calls["n"] == 2
    assert ir3["src_len"] != ir1["src_len"]


def test_ir_cache_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AINL_IR_CACHE", "0")
    monkeypatch.setenv("AINL_IR_CACHE_DIR", str(tmp_path / "cache"))

    src = tmp_path / "x.ainl"
    src.write_text("S core cron \"0 * * * *\"\nL0:\n  J 0\n", encoding="utf-8")
    n = 0

    def fake_compile(text: str) -> dict:
        nonlocal n
        n += 1
        return {"n": n}

    compile_source_cached(src, fake_compile)
    compile_source_cached(src, fake_compile)
    assert n == 2


def test_save_load_meta_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AINL_IR_CACHE", "1")
    monkeypatch.setenv("AINL_IR_CACHE_DIR", str(tmp_path / "c"))

    src = tmp_path / "a.ainl"
    src.write_text("L0:\n  J 1\n", encoding="utf-8")
    ir = {"x": 1}
    save_cached_ir(src, ir)
    assert load_cached_ir(src) == ir

    # Corrupt meta -> miss
    stat = src.stat()
    meta_p = _mod._meta_path(src, stat)
    meta_p.write_text(json.dumps({"path": "wrong"}), encoding="utf-8")
    assert load_cached_ir(src) is None
