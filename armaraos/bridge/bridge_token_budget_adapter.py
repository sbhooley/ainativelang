"""Shim: delegates to ``openclaw/bridge/bridge_token_budget_adapter.py``.

---------------------------------------------------------------------------
WHY importlib + A DISTINCT MODULE NAME (do not "simplify" to import *)
---------------------------------------------------------------------------

``armaraos/bridge/runner.py`` loads **this path** with::

    importlib.util.spec_from_file_location(
        "bridge_token_budget_adapter",
        _BRIDGE_DIR / "bridge_token_budget_adapter.py",
    )

So during ``exec_module``, the interpreter already has a module object registered
under the name ``bridge_token_budget_adapter`` pointing at **this file**.

A tempting "thin shim" is::

    sys.path.insert(0, "<repo>/openclaw/bridge")
    from bridge_token_budget_adapter import *   # noqa

That resolves ``bridge_token_budget_adapter`` to the **same partially-loaded
module** (this shim), not the OpenClaw implementation — circular import, wrong
or empty exports, and subtle breakage.

**Canonical pattern:** load the real implementation file with
``spec_from_file_location`` using a **different** ``name`` (e.g.
``openclaw_internal.bridge_token_budget_adapter``), ``exec_module`` into that
object, then assign ``BridgeTokenBudgetAdapter`` (and any future public symbols)
from that module onto this one. No ``sys.path`` mutation; one source of truth
under ``openclaw/bridge/``.

If you add more exports, pull them from ``_impl`` explicitly; do not star-import
the real module by the basename ``bridge_token_budget_adapter``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# armaraos/bridge/this_file -> armaraos -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL = _REPO_ROOT / "openclaw" / "bridge" / "bridge_token_budget_adapter.py"

_spec = importlib.util.spec_from_file_location(
    "openclaw_internal.bridge_token_budget_adapter",
    _REAL,
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load spec for bridge token budget adapter: {_REAL}")
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

BridgeTokenBudgetAdapter = _impl.BridgeTokenBudgetAdapter

__all__ = ["BridgeTokenBudgetAdapter"]
