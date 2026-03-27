"""Emit target identifiers shared by ``compiler_v2`` IR and benchmark tooling.

Keeping these lists in one module avoids drift between ``required_emit_targets`` in the
compiler and ``tooling.emission_planner.TARGET_ORDER``.
"""

from __future__ import annotations

# Historical six-target multitarget set (compiler-backed emitters only).
CORE_EMIT_TARGET_ORDER = [
    "react_ts",
    "python_api",
    "prisma",
    "mt5",
    "scraper",
    "cron",
]

# Full multitarget set including standalone hybrid wrapper scripts
# (``scripts/emit_langgraph.py``, ``scripts/emit_temporal.py``).
#
# Host-specific outputs (e.g. Hermes skill bundles) are supported via dedicated
# CLI emitters and are intentionally excluded from this multi-target set so
# capability planning and emission ordering remain stable.
FULL_EMIT_TARGET_ORDER = list(CORE_EMIT_TARGET_ORDER) + ["langgraph", "temporal"]
