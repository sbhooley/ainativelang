"""Tests for ``cli.main._register_enabled_adapters`` and the spec table.

Focused on the public contract of the spec-driven registration loop: which
adapters register, when, and which always-on. Includes a regression test
for the wasm-under-api nesting bug introduced by 818d5a3 and fixed in this
PR.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cli.main import _ADAPTER_SPECS, _register_enabled_adapters
from runtime.adapters.base import AdapterRegistry


def _minimal_args(**overrides) -> SimpleNamespace:
    """Build a minimal argparse-like Namespace.

    Only attributes consulted without ``getattr(default=...)`` need to be
    populated; the spec factories use ``getattr`` for their adapter-specific
    args so missing attrs default cleanly.
    """
    base = {"enable_adapter": []}
    base.update(overrides)
    return SimpleNamespace(**base)


def _registry_allowing_all() -> AdapterRegistry:
    # Allow every spec name plus the always-on extras the registration loop
    # adds. Tests don't go through the validate gate so any name is fine.
    allowed = [s.name for s in _ADAPTER_SPECS]
    return AdapterRegistry(allowed=allowed)


def test_always_on_adapters_register_with_no_enable_flags():
    args = _minimal_args()
    reg = _registry_allowing_all()
    _register_enabled_adapters(reg, args)
    for name in ("memory", "fanout", "cache", "web", "tiktok", "queue", "browser"):
        assert name in reg, f"{name} should always register"


def test_wasm_and_api_are_independent_in_spec_table():
    """Regression (structural): 818d5a3 indented wasm registration under
    ``if "api" in enabled`` so wasm only registered when api was enabled.
    After the spec-table refactor wasm and api are sibling entries in
    ``_ADAPTER_SPECS`` -- this assertion makes the structural decoupling
    explicit so a future change can't reintroduce the conflation without
    failing here. Does not require wasmtime to be installed."""
    by_name = {s.name: s for s in _ADAPTER_SPECS}
    assert "wasm" in by_name and "api" in by_name
    assert not by_name["wasm"].always_on
    assert not by_name["api"].always_on
    # Neither one should depend on the other's enablement.
    assert by_name["wasm"].extra_enable_env is None
    assert by_name["api"].extra_enable_env is None


def test_wasm_registers_without_api_enabled():
    """End-to-end variant of the regression test: actually invoke the
    factory loop and assert wasm registers, api does not. Requires
    ``wasmtime`` because :class:`WasmAdapter`'s constructor refuses to
    initialize without it."""
    pytest.importorskip("wasmtime")
    args = _minimal_args(
        enable_adapter=["wasm"],
        wasm_module=["m1=/tmp/does-not-need-to-exist.wasm"],
        wasm_allow_module=None,
    )
    reg = _registry_allowing_all()
    _register_enabled_adapters(reg, args)
    assert "wasm" in reg, "wasm must register on its own enablement"
    assert "api" not in reg, "api must not register implicitly"


def test_wasm_factory_requires_at_least_one_module():
    pytest.importorskip("wasmtime")
    args = _minimal_args(enable_adapter=["wasm"], wasm_module=[], wasm_allow_module=None)
    reg = _registry_allowing_all()
    with pytest.raises(SystemExit):
        _register_enabled_adapters(reg, args)


def test_ptc_runner_env_fallback_enables_adapter():
    """``AINL_ENABLE_PTC=true`` must enable ptc_runner without --enable-adapter."""
    import os

    args = _minimal_args(http_allow_host=[], http_timeout_s=5.0, http_max_response_bytes=1_000_000)
    reg = _registry_allowing_all()
    prev = os.environ.get("AINL_ENABLE_PTC")
    os.environ["AINL_ENABLE_PTC"] = "true"
    try:
        _register_enabled_adapters(reg, args)
    finally:
        if prev is None:
            os.environ.pop("AINL_ENABLE_PTC", None)
        else:
            os.environ["AINL_ENABLE_PTC"] = prev
    assert "ptc_runner" in reg


def test_a2a_requires_explicit_host_or_local_opt_in():
    args = _minimal_args(enable_adapter=["a2a"])
    reg = _registry_allowing_all()
    with pytest.raises(SystemExit):
        _register_enabled_adapters(reg, args)


def test_spec_table_has_no_duplicate_names():
    names = [s.name for s in _ADAPTER_SPECS]
    assert len(names) == len(set(names)), f"duplicate adapter spec names: {names}"
