"""ArmaraOS integration helpers for the bridge runner.

``armaraos_monitor_registry`` returns a runtime :class:`~runtime.adapters.base.AdapterRegistry`
with ArmaraOS bridge adapters **allowed and registered** up front so capability
intersection and ``adapter not registered`` failures do not depend on each caller
re-wiring the same three adapters.
"""

from __future__ import annotations

from adapters.armaraos_defaults import ARMARAOS_MONITOR_PRESEEDED_ADAPTERS
from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge
from armaraos.bridge.bridge_token_budget_adapter import BridgeTokenBudgetAdapter
from armaraos.bridge.cron_drift_check import CronDriftCheckAdapter
from runtime.adapters.base import AdapterRegistry


def armaraos_monitor_registry() -> AdapterRegistry:
    """Runtime registry with core + ArmaraOS bridge adapters pre-registered."""
    reg = AdapterRegistry()
    for name in ARMARAOS_MONITOR_PRESEEDED_ADAPTERS:
        reg.allow(name)
    reg.register(AINLGraphMemoryBridge.NAME, AINLGraphMemoryBridge())
    reg.register("bridge", BridgeTokenBudgetAdapter())
    reg.register(CronDriftCheckAdapter.NAME, CronDriftCheckAdapter())
    return reg

