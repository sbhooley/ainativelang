"""
Environment-driven caps for graph memory JSON load/export.

Large ArmaraOS graph snapshots + ``export_graph`` + bundle export can materialize
multi‑gigabyte Python object graphs and freeze the host. These knobs bound **file
read size**, **nodes ingested per file**, **export fan‑out**, and **bundle
preload** size.

All limits are soft defaults; operators raise caps via env when justified.

Environment variables
-----------------------
``AINL_GRAPH_MEMORY_MAX_JSON_BYTES``
    Max on-disk bytes per JSON file before ``json.loads`` in :class:`GraphStore`
    load paths (main graph file + ArmaraOS snapshot). Default: 150 MiB.

``AINL_GRAPH_MEMORY_MAX_NODES``
    Max ``nodes`` rows ingested from a single decoded JSON object (main store +
    snapshot). Default: 120_000. Use ``0`` for unlimited.

``AINL_GRAPH_EXPORT_MAX_NODES`` / ``AINL_GRAPH_EXPORT_MAX_EDGES``
    Caps for :meth:`GraphStore.export_graph` (and bundle snapshots). Defaults:
    50_000 nodes, 250_000 edges. When truncated, newest nodes by ``created_at``
    are kept. ``0`` = unlimited.

``AINL_GRAPH_MEMORY_MAX_PERSONA_TRAITS``
    Max persona traits returned from ``persona_load``. Default: 20_000.

``AINL_BUNDLE_MAX_FILE_BYTES``
    Max ``bundle.ainlbundle`` size for :meth:`AINLGraphMemoryBridge.boot`
    preload. Default: 80 MiB.

``AINL_BUNDLE_RLIMIT_AS_BYTES`` (Unix)
    If set to a positive integer, apply ``resource.RLIMIT_AS`` (address-space
    ceiling) in bundle-export subprocesses. Best-effort; ignored if unsupported.
"""

from __future__ import annotations

import os
from typing import Optional


def _parse_int(raw: str) -> Optional[int]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def env_int(name: str, default: int) -> int:
    """Non-negative int from env; invalid/missing → ``default``."""
    v = _parse_int(os.environ.get(name) or "")
    if v is None:
        return max(0, default)
    return max(0, v)


def env_int_or_unlimited(name: str, default: int) -> Optional[int]:
    """
    Positive int cap, or ``None`` if env is ``0`` / ``unlimited`` / ``none``
    (case-insensitive) meaning no cap.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    if raw.lower() in ("0", "none", "unlimited", "off", "false", "-1"):
        return None
    try:
        v = int(raw)
    except ValueError:
        return default
    if v <= 0:
        return None
    return v


def env_bytes(name: str, default: int) -> int:
    """Byte ceiling from env (non-negative int)."""
    return env_int(name, default)


def max_json_bytes() -> int:
    return env_bytes("AINL_GRAPH_MEMORY_MAX_JSON_BYTES", 150 * 1024 * 1024)


def max_nodes_per_json() -> Optional[int]:
    return env_int_or_unlimited("AINL_GRAPH_MEMORY_MAX_NODES", 120_000)


def export_max_nodes() -> Optional[int]:
    return env_int_or_unlimited("AINL_GRAPH_EXPORT_MAX_NODES", 50_000)


def export_max_edges() -> Optional[int]:
    return env_int_or_unlimited("AINL_GRAPH_EXPORT_MAX_EDGES", 250_000)


def max_persona_traits() -> int:
    return env_int("AINL_GRAPH_MEMORY_MAX_PERSONA_TRAITS", 20_000)


def max_bundle_file_bytes() -> int:
    return env_bytes("AINL_BUNDLE_MAX_FILE_BYTES", 80 * 1024 * 1024)


def maybe_apply_address_space_limit() -> None:
    """Optional hard RAM/virtual ceiling for the current process (bundle cron)."""
    raw = (os.environ.get("AINL_BUNDLE_RLIMIT_AS_BYTES") or "").strip()
    if not raw:
        return
    try:
        lim = int(raw)
    except ValueError:
        return
    if lim <= 0:
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    except Exception:
        # Best-effort: platform may not support RLIMIT_AS the same way.
        return
