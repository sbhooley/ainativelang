"""Tests for services.tool_surface / ToolPatch narrowing (AINL_SPEC §7)."""

from __future__ import annotations

import pytest

from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterRegistry
from runtime.engine import AinlRuntimeError, RuntimeEngine, ERROR_CODE_TOOL_PATCH_DENY


def test_runtime_tool_patch_denies_r_when_adapter_not_in_allowlist():
    code = '''
L1:
R http.GET "http://example.com" ->r
J r
'''
    ir = AICodeCompiler(strict_mode=False).compile(code)
    assert not ir.get("errors"), ir.get("errors")
    ir.setdefault("services", {})["tool_surface"] = {"adapter_allow": ["core"], "schema_version": 1}
    eng = RuntimeEngine(ir, AdapterRegistry(allowed=["core", "http"]), execution_mode="steps-only")
    with pytest.raises(AinlRuntimeError) as ei:
        eng.run_label("1", {})
    assert ei.value.code == ERROR_CODE_TOOL_PATCH_DENY
    assert ei.value.data.get("dispatch_key") == "http"


def test_runtime_tool_patch_allows_core_when_patch_lists_core():
    code = '''
L1:
R core.ADD 1 2 ->x
J x
'''
    ir = AICodeCompiler(strict_mode=False).compile(code)
    assert not ir.get("errors"), ir.get("errors")
    ir.setdefault("services", {})["tool_surface"] = {"adapter_allow": ["core"], "schema_version": 1}
    eng = RuntimeEngine(ir, AdapterRegistry(allowed=["core"]), execution_mode="steps-only")
    assert eng.run_label("1", {}) == 3


def test_compile_preserves_host_tool_surface_via_preserved_services():
    code = "L1: R core.ADD 1 2 ->x J x\n"
    ts = {"adapter_allow": ["core", "http"], "schema_version": 1}
    ir = AICodeCompiler(strict_mode=False).compile(code, preserved_services={"tool_surface": ts})
    assert ir["services"]["tool_surface"]["adapter_allow"] == ["core", "http"]


def test_patch_profile_resolves_adapter_allow():
    """patch_profile ``http_core`` supplies adapter_allow when absent."""
    code = '''
L1:
R http.GET "http://example.com" ->r
J r
'''
    ir = AICodeCompiler(strict_mode=False).compile(
        code,
        preserved_services={"tool_surface": {"patch_profile": "http_core", "schema_version": 1}},
    )
    assert not ir.get("errors"), ir.get("errors")
    ts = ir["services"]["tool_surface"]
    assert set(ts.get("adapter_allow") or []) >= {"core", "http"}


def test_strict_unknown_patch_profile_errors():
    ir = AICodeCompiler(strict_mode=True).compile(
        "L1: R core.ADD 1 2 ->x J x\n",
        preserved_services={"tool_surface": {"patch_profile": "no_such_profile_v1"}},
    )
    assert ir.get("errors")


def test_strict_compile_errors_when_tool_surface_excludes_required_adapter():
    code = "L1: R core.ADD 1 2 ->x J x\n"
    ts = {"adapter_allow": ["http"], "schema_version": 1}
    ir = AICodeCompiler(strict_mode=True).compile(code, preserved_services={"tool_surface": ts})
    errs = ir.get("errors") or []
    assert errs
    assert any("registry key 'core'" in e for e in errs)
