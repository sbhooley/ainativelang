"""ArmaraOS integration helpers for the bridge runner and other hosts.

Use :func:`build_armaraos_monitor_registry` to obtain a runtime
:class:`~runtime.adapters.base.AdapterRegistry` with ArmaraOS bridge adapters
**allowed and registered** (``ainl_graph_memory``, ``bridge``, ``cron_drift_check``)
so capability intersection and ``adapter not registered`` failures do not depend
on each caller re-wiring the same adapters.

**Capability contract:** pre-seeded adapters are both ``allow()``\\ed and
``register()``\\ed here. Hosts only ``allow`` / ``register`` *additional*
adapters (for example ``github``, ``crm``). They must not need to remember the
pre-seeded names unless a security profile explicitly narrows the allowlist.

**Graph memory lifecycle:** :func:`build_armaraos_monitor_registry` does **not**
call :meth:`armaraos.bridge.ainl_graph_memory.AINLGraphMemoryBridge.boot` unless
``boot_graph_memory=True``. Full bridge hosts register extra adapters first, then
call :func:`boot_armaraos_graph_memory` once (see ``armaraos/bridge/runner.py``).
**Inbox write-back** to ArmaraOS SQLite (**``ainl_graph_memory_inbox.json``**) is
handled by :class:`armaraos.bridge.ainl_memory_sync.AinlMemorySyncWriter` from the
bridge and runner; see ``armaraos/docs/graph-memory-sync.md``.
"""

from __future__ import annotations

from adapters.armaraos_defaults import ARMARAOS_MONITOR_PRESEEDED_ADAPTERS
from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge
from armaraos.bridge.bridge_token_budget_adapter import BridgeTokenBudgetAdapter
from armaraos.bridge.cron_drift_check import CronDriftCheckAdapter
from runtime.adapters.base import AdapterError, AdapterRegistry


def boot_armaraos_graph_memory(reg: AdapterRegistry, agent_id: str = "armaraos") -> AINLGraphMemoryBridge:
    """Run :meth:`AINLGraphMemoryBridge.boot` on the registry's graph-memory adapter.

    Retrieves the adapter via the public :meth:`AdapterRegistry.get` API (no
    private registry fields).

    Each call records a new episodic **bridge_boot** node. Hosts that want a
    single boot record per process should invoke this once after all adapters
    are registered; repeated calls remain safe and are useful for tests or
    intentional re-bootstrap.
    """
    raw = reg.get(AINLGraphMemoryBridge.NAME)
    if not isinstance(raw, AINLGraphMemoryBridge):
        got = "None" if raw is None else type(raw).__name__
        raise AdapterError(
            f"expected adapter {AINLGraphMemoryBridge.NAME!r} to be an AINLGraphMemoryBridge, got {got!r}"
        )
    raw.boot(agent_id=agent_id)
    return raw


def build_armaraos_monitor_registry(
    *,
    agent_id: str = "armaraos",
    boot_graph_memory: bool = False,
) -> AdapterRegistry:
    """Create a registry with pre-seeded ArmaraOS bridge adapters (allowed + registered).

    Parameters
    ----------
    agent_id:
        Passed to :func:`boot_armaraos_graph_memory` when ``boot_graph_memory`` is true.
    boot_graph_memory:
        When true, calls :func:`boot_armaraos_graph_memory` immediately after registration
        (monitor-only hosts). Bridge runners that add more adapters first should pass
        ``False`` and call :func:`boot_armaraos_graph_memory` after their own registrations.
    """
    reg = AdapterRegistry()
    for name in ARMARAOS_MONITOR_PRESEEDED_ADAPTERS:
        reg.allow(name)
    reg.register(AINLGraphMemoryBridge.NAME, AINLGraphMemoryBridge())
    reg.register("bridge", BridgeTokenBudgetAdapter())
    reg.register(CronDriftCheckAdapter.NAME, CronDriftCheckAdapter())
    if boot_graph_memory:
        boot_armaraos_graph_memory(reg, agent_id=agent_id)
    return reg


def armaraos_monitor_registry() -> AdapterRegistry:
    """Registry with pre-seeded ArmaraOS adapters; does **not** call graph ``boot``."""
    return build_armaraos_monitor_registry(boot_graph_memory=False)
