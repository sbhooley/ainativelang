"""ArmaraOS defaults for integration adapters.

Keep these values aligned with OpenClaw where the underlying services are shared.
"""

from __future__ import annotations

from adapters.openclaw_defaults import DEFAULT_CRM_HEALTH_URL  # re-export

# Adapter names pre-seeded by ``adapters.armaraos_integration.armaraos_monitor_registry``
# (bridge token budget is registered under the IR name ``bridge``).
ARMARAOS_MONITOR_PRESEEDED_ADAPTERS: tuple[str, ...] = (
    "ainl_graph_memory",
    "bridge",
    "cron_drift_check",
)

