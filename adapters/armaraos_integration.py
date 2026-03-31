"""ArmaraOS integration helpers for the bridge runner.

This is intentionally small: the ArmaraOS bridge runner builds its own runtime
AdapterRegistry and then applies capability gates via tooling.capability_grant.
"""

from __future__ import annotations

from runtime.adapters.base import AdapterRegistry


def armaraos_monitor_registry() -> AdapterRegistry:
    """Create an empty runtime adapter registry (core allowed by default)."""
    return AdapterRegistry()

