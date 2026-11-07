"""Smoke tests for core.substr / core.env used by intelligence/*.lang workflows."""

from __future__ import annotations

from runtime.engine import RuntimeEngine


def test_x_core_substr_date_prefix():
    code = """
S app t /t
L1:
  X d (core.substr "2026-03-16T12:00:00Z" 0 10)
  J d
"""
    eng = RuntimeEngine.from_code(code, strict=False)
    assert eng.run_label("1", {}) == "2026-03-16"


def test_x_core_env_default():
    code = """
S app t /t
L1:
  X v (core.env "AINL_TEST_NONEXISTENT_ENV_KEY_XYZ" "fallback")
  J v
"""
    eng = RuntimeEngine.from_code(
        code,
        strict=False,
        limits={"env_allowlist": ["AINL_TEST_NONEXISTENT_ENV_KEY_XYZ"]},
    )
    assert eng.run_label("1", {}) == "fallback"


def test_r_core_substr_via_adapter():
    code = """
S app t /t
L1:
  R core substr "abcdef" 2 3 ->s
  J s
"""
    eng = RuntimeEngine.from_code(code, strict=False)
    assert eng.run_label("1", {}) == "cde"
