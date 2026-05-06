"""
Tool surface / ToolPatch helpers for ``services.tool_surface`` (AINL_SPEC §7).

Registry dispatch keys align with :class:`runtime.adapters.base.AdapterRegistry` names
(``core``, ``http``, ``ainl_graph_memory``, …), not strict adapter contract strings.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set

_PATCH_PROFILES_CACHE: Optional[Dict[str, Any]] = None


def _patch_profiles_path() -> Path:
    return Path(__file__).resolve().parent / "patch_profiles.json"


def load_patch_profiles() -> Dict[str, Dict[str, Any]]:
    """Return merged patch profile definitions (builtin JSON + optional env overlay)."""
    global _PATCH_PROFILES_CACHE
    if _PATCH_PROFILES_CACHE is not None:
        return _PATCH_PROFILES_CACHE

    profiles: Dict[str, Dict[str, Any]] = {}
    base_path = _patch_profiles_path()
    if base_path.is_file():
        try:
            raw = json.loads(base_path.read_text(encoding="utf-8"))
            inner = raw.get("profiles") if isinstance(raw, dict) else None
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if isinstance(v, dict):
                        profiles[str(k)] = dict(v)
        except Exception:
            pass

    extra = str(os.environ.get("AINL_PATCH_PROFILES_JSON") or "").strip()
    if extra:
        try:
            p = Path(extra).expanduser()
            if p.is_file():
                raw = json.loads(p.read_text(encoding="utf-8"))
                inner = raw.get("profiles") if isinstance(raw, dict) else raw
                if isinstance(inner, dict):
                    for k, v in inner.items():
                        if isinstance(v, dict):
                            profiles[str(k)] = dict(v)
        except Exception:
            pass

    _PATCH_PROFILES_CACHE = profiles
    return profiles


def adapter_allow_for_profile(patch_profile: str) -> Optional[Set[str]]:
    """Resolve ``adapter_allow`` set for a named ``patch_profile``, if known."""
    name = str(patch_profile or "").strip()
    if not name:
        return None
    prof = load_patch_profiles().get(name)
    if not isinstance(prof, dict):
        return None
    aa = prof.get("adapter_allow")
    if not isinstance(aa, list) or not aa:
        return None
    out = {str(x).strip() for x in aa if x is not None and str(x).strip()}
    return out or None


def effective_tool_surface(tool_surface: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Apply ``patch_profile`` → builtin/env profiles and intersect with explicit ``adapter_allow``.

    - Profile only: use profile's ``adapter_allow``.
    - Explicit ``adapter_allow`` only: unchanged.
    - Both: set ``adapter_allow`` to the **intersection** (tightest patch).
    - Unknown ``patch_profile``: leaves ``adapter_allow`` unchanged (strict compile adds an error).
    """
    if tool_surface is None:
        return None
    if not isinstance(tool_surface, dict):
        return None
    out = copy.deepcopy(tool_surface)
    pname = str(out.get("patch_profile") or "").strip()
    profile_allow = adapter_allow_for_profile(pname) if pname else None
    explicit_aa = out.get("adapter_allow")
    explicit_set: Optional[Set[str]] = None
    if isinstance(explicit_aa, list) and explicit_aa:
        explicit_set = {str(x).strip() for x in explicit_aa if x is not None and str(x).strip()}
    if profile_allow is not None and explicit_set is not None:
        inter = sorted(profile_allow & explicit_set)
        out["adapter_allow"] = inter
    elif profile_allow is not None:
        out["adapter_allow"] = sorted(profile_allow)
    return out


def adapter_allow_set(tool_surface: Any) -> Optional[Set[str]]:
    """Return the effective adapter allow-set for runtime/registry narrowing.

    ``services.tool_surface.adapter_allow`` lists registry adapter names **after**
    routing (e.g. ``ainl_graph_memory`` for ``memory.recall``, not ``memory``).

    An empty JSON array is treated as *unset* (no narrowing) to avoid accidental
    total lockout; omit the key or use non-empty lists for enforcement.
    """
    if not isinstance(tool_surface, dict):
        return None
    aa = tool_surface.get("adapter_allow")
    if not isinstance(aa, list) or not aa:
        return None
    out = {str(x).strip() for x in aa if x is not None and str(x).strip()}
    return out or None


def dispatch_registry_key(adapter: str, module_aliases: Dict[str, str]) -> str:
    """Map an ``R`` step ``adapter`` field to a registry / capability key."""
    adapter = str(adapter or "").strip()
    if not adapter:
        return ""
    if "." not in adapter:
        return adapter.lower()
    adp_name, verb = adapter.split(".", 1)
    adp_l = adp_name.lower()
    full = module_aliases.get(adapter, adapter)
    sub = full.split(".", 1)[1].lower() if "." in full else str(verb).lower()
    if sub == "export":
        sub = "export_graph"
    if sub == "store":
        sub = "store_pattern"
    if adp_l == "persona":
        return "ainl_graph_memory"
    if adp_l == "memory":
        if sub in ("recall", "search", "export_graph", "store_pattern", "pattern_recall", "execute", "patch"):
            return "ainl_graph_memory"
        return "memory"
    return adp_l


def registry_dispatch_key_for_step(step: Dict[str, Any], module_aliases: Dict[str, str]) -> str:
    """Best-effort registry key for a legacy IR step dict (``op`` + adapter fields)."""
    st = step or {}
    op = str(st.get("op") or "").strip()
    if op in ("QueuePut",):
        return "queue"
    if op in ("CacheGet", "CacheSet"):
        return "cache"
    if op in ("memory.merge", "MemoryMerge"):
        return "memory"
    if op in ("MemoryRecall", "MemorySearch", "MemoryExecute", "MemoryPatch"):
        return "ainl_graph_memory"
    if op == "persona.update":
        return "ainl_graph_memory"
    if op != "R":
        return ""
    adapter = str(st.get("adapter") or "").strip()
    if not adapter:
        src = str(st.get("src") or "").strip()
        req_op = str(st.get("req_op") or "").strip()
        adapter = f"{src}.{req_op}" if src and req_op else src
    if not adapter:
        return ""
    return dispatch_registry_key(adapter, module_aliases)


def narrow_allowed_adapters(allowed: list[str], tool_surface: Any) -> tuple[list[str], Optional[Set[str]]]:
    """Intersect host/IR-allowed adapters with ``tool_surface.adapter_allow``."""
    patch = adapter_allow_set(tool_surface)
    if not patch:
        return list(allowed), None
    allowed_set = set(allowed)
    inter = sorted(allowed_set & patch)
    return inter, patch


def validate_tool_surface_shape(tool_surface: Any) -> list[str]:
    """Lightweight shape validation (no external JSON Schema dependency)."""
    if tool_surface is None:
        return []
    if not isinstance(tool_surface, dict):
        return ["services.tool_surface must be an object"]
    errs: list[str] = []
    aa = tool_surface.get("adapter_allow")
    if aa is not None and not isinstance(aa, list):
        errs.append("tool_surface.adapter_allow must be an array when present")
    ea = tool_surface.get("explicit_allow")
    if ea is not None and not isinstance(ea, list):
        errs.append("tool_surface.explicit_allow must be an array when present")
    pp = tool_surface.get("patch_profile")
    if pp is not None and not isinstance(pp, str):
        errs.append("tool_surface.patch_profile must be a string when present")
    rr = tool_surface.get("registry_ref")
    if rr is not None and not isinstance(rr, str):
        errs.append("tool_surface.registry_ref must be a string when present")
    return errs


def validate_patch_profile_known(patch_profile: Optional[str], *, strict: bool) -> list[str]:
    """If ``patch_profile`` is set, ensure it exists in ``load_patch_profiles()`` when ``strict``."""
    name = str(patch_profile or "").strip()
    if not name or not strict:
        return []
    if name in load_patch_profiles():
        return []
    return [
        f"Unknown services.tool_surface.patch_profile {name!r}; "
        f"define it in tooling/patch_profiles.json, "
        f"extend via AINL_PATCH_PROFILES_JSON, or remove patch_profile."
    ]
