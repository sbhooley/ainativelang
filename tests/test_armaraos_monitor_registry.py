"""ArmaraOS monitor registry + public adapter lookup contract."""
from __future__ import annotations

import inspect
import os

import pytest

from adapters.armaraos_defaults import ARMARAOS_MONITOR_PRESEEDED_ADAPTERS
from adapters.armaraos_integration import (
    armaraos_monitor_registry,
    boot_armaraos_graph_memory,
    build_armaraos_monitor_registry,
)
from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge
from runtime.adapters.base import AdapterError, AdapterRegistry


def test_armaraos_monitor_registry_preseeds_expected_adapters() -> None:
    reg = armaraos_monitor_registry()
    for name in ARMARAOS_MONITOR_PRESEEDED_ADAPTERS:
        assert name in reg
        assert reg.get(name) is not None
    assert isinstance(reg.get(AINLGraphMemoryBridge.NAME), AINLGraphMemoryBridge)
    reg.call("cron_drift_check", "report", [], {})
    reg.call("bridge", "rolling_budget_json", [], {})


def test_registry_public_get_returns_preseeded_graph_bridge() -> None:
    reg = build_armaraos_monitor_registry(boot_graph_memory=False)
    gm = reg.get(AINLGraphMemoryBridge.NAME)
    assert isinstance(gm, AINLGraphMemoryBridge)


def test_build_armaraos_monitor_registry_boots_graph_memory() -> None:
    prev_bundle = os.environ.pop("AINL_BUNDLE_PATH", None)
    try:
        reg = build_armaraos_monitor_registry(boot_graph_memory=True)
        gm = reg.get(AINLGraphMemoryBridge.NAME)
        assert isinstance(gm, AINLGraphMemoryBridge)
        boot_nodes = [n for n in gm._store.all_nodes() if getattr(n, "label", None) == "bridge_boot"]
        assert len(boot_nodes) >= 1
    finally:
        if prev_bundle is not None:
            os.environ["AINL_BUNDLE_PATH"] = prev_bundle


def test_runner_uses_shared_registry_bootstrap_without_private_access() -> None:
    src = inspect.getsource(
        __import__("armaraos.bridge.runner", fromlist=["build_wrapper_registry"]).build_wrapper_registry
    )
    assert "_adapters" not in src


def test_armaraos_monitor_registry_idempotent_bootstrap() -> None:
    reg = armaraos_monitor_registry()
    b1 = boot_armaraos_graph_memory(reg, agent_id="armaraos")
    b2 = boot_armaraos_graph_memory(reg, agent_id="armaraos")
    assert b1 is b2 is reg.get(AINLGraphMemoryBridge.NAME)


def test_boot_armaraos_graph_memory_requires_bridge() -> None:
    reg = AdapterRegistry()
    reg.allow(AINLGraphMemoryBridge.NAME)
    with pytest.raises(AdapterError):
        boot_armaraos_graph_memory(reg, agent_id="armaraos")
