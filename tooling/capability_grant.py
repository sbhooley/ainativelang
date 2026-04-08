"""Capability grant model for AINL execution surfaces.

A capability grant constrains what a caller (or server) is allowed to do.
Grants are **restrictive-only**: merging two grants always produces a
result that is at least as restricted as either input.

Merge rules:
  - ``allowed_adapters``: intersection (narrowing)
  - ``forbidden_adapters``: union (widening)
  - ``forbidden_effects``: union
  - ``forbidden_effect_tiers``: union
  - ``forbidden_privilege_tiers``: union
  - ``limits``: per-key minimum (more restrictive wins)
  - ``adapter_constraints``: per-adapter, per-field intersection for lists,
    min for numbers, AND for booleans

This module does not change AINL language or IR semantics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


GRANT_KEYS_FORBIDDEN_SETS = (
    "forbidden_adapters",
    "forbidden_effects",
    "forbidden_effect_tiers",
    "forbidden_privilege_tiers",
)

GRANT_LIMIT_KEYS = (
    "max_steps",
    "max_depth",
    "max_adapter_calls",
    "max_time_ms",
    "max_frame_bytes",
    "max_loop_iters",
)


def env_truthy(val: Any) -> bool:
    """True for common affirmative env var spellings (1, true, yes, on)."""
    s = str(val or "").strip().lower()
    return s in {"1", "true", "yes", "on"}


def empty_grant() -> Dict[str, Any]:
    """Return a maximally permissive (empty) grant."""
    return {
        "allowed_adapters": None,
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": {},
        "adapter_constraints": {},
    }


def merge_grants(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Restrictively merge *overlay* on top of *base*.

    The result is always at least as restricted as either input.
    """
    merged: Dict[str, Any] = {}

    # --- allowed_adapters: intersection ---------------------------------
    base_aa = base.get("allowed_adapters")
    overlay_aa = overlay.get("allowed_adapters")
    if base_aa is None and overlay_aa is None:
        merged["allowed_adapters"] = None
    elif base_aa is None:
        merged["allowed_adapters"] = sorted(set(overlay_aa))
    elif overlay_aa is None:
        merged["allowed_adapters"] = sorted(set(base_aa))
    else:
        merged["allowed_adapters"] = sorted(set(base_aa) & set(overlay_aa))

    # --- forbidden_* sets: union ----------------------------------------
    for key in GRANT_KEYS_FORBIDDEN_SETS:
        base_set = set(base.get(key) or [])
        overlay_set = set(overlay.get(key) or [])
        combined = sorted(base_set | overlay_set)
        merged[key] = combined

    # --- limits: per-key minimum ----------------------------------------
    base_lim = base.get("limits") or {}
    overlay_lim = overlay.get("limits") or {}
    all_keys = set(base_lim) | set(overlay_lim)
    lim: Dict[str, int] = {}
    for k in sorted(all_keys):
        bv = base_lim.get(k)
        ov = overlay_lim.get(k)
        if bv is not None and ov is not None:
            lim[k] = min(int(bv), int(ov))
        elif bv is not None:
            lim[k] = int(bv)
        else:
            lim[k] = int(ov)  # type: ignore[arg-type]
    merged["limits"] = lim

    # --- adapter_constraints: per-adapter merge -------------------------
    base_ac = base.get("adapter_constraints") or {}
    overlay_ac = overlay.get("adapter_constraints") or {}
    ac: Dict[str, Dict[str, Any]] = {}
    for adapter in sorted(set(base_ac) | set(overlay_ac)):
        bc = base_ac.get(adapter) or {}
        oc = overlay_ac.get(adapter) or {}
        merged_c: Dict[str, Any] = {}
        for field in sorted(set(bc) | set(oc)):
            bval = bc.get(field)
            oval = oc.get(field)
            if isinstance(bval, list) and isinstance(oval, list):
                merged_c[field] = sorted(set(bval) & set(oval))
            elif isinstance(bval, list):
                merged_c[field] = bval
            elif isinstance(oval, list):
                merged_c[field] = oval
            elif isinstance(bval, (int, float)) and isinstance(oval, (int, float)):
                merged_c[field] = min(bval, oval)
            elif isinstance(bval, bool) and isinstance(oval, bool):
                merged_c[field] = bval and oval
            elif bval is not None:
                merged_c[field] = bval
            else:
                merged_c[field] = oval
        ac[adapter] = merged_c
    merged["adapter_constraints"] = ac

    return merged


def grant_to_policy(grant: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the policy-validator-compatible subset from a grant."""
    policy: Dict[str, Any] = {}
    for key in GRANT_KEYS_FORBIDDEN_SETS:
        vals = grant.get(key) or []
        if vals:
            policy[key] = list(vals)
    return policy


def grant_to_limits(grant: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the limits dict from a grant."""
    return dict(grant.get("limits") or {})


def grant_to_allowed_adapters(
    grant: Dict[str, Any], fallback: Optional[List[str]] = None
) -> Optional[List[str]]:
    """Return the host adapter allowlist derived from a grant.

    - If ``allowed_adapters`` is a list (including empty), return a copy: the
      runtime intersects IR-required adapters with this list.
    - If it is ``None`` and *fallback* is provided, return ``list(fallback)``.
    - If it is ``None`` and *fallback* is omitted, return ``None``: no host
      allowlist (IR-declared adapters apply; ``AINL_HOST_ADAPTER_ALLOWLIST``
      may still restrict).
    """
    aa = grant.get("allowed_adapters")
    if aa is not None:
        return list(aa)
    if fallback is not None:
        return list(fallback)
    return None


def load_profile_as_grant(profile_name: str) -> Dict[str, Any]:
    """Load a named security profile and convert it to a capability grant.

    The profile is read from ``tooling/security_profiles.json``.
    """
    profiles_path = Path(__file__).resolve().parent / "security_profiles.json"
    try:
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raise ValueError(f"cannot load security profiles from {profiles_path}")

    profile = (profiles.get("profiles") or {}).get(profile_name)
    if profile is None:
        available = sorted((profiles.get("profiles") or {}).keys())
        raise ValueError(
            f"unknown security profile {profile_name!r}; "
            f"available: {available}"
        )

    aa = profile.get("adapter_allowlist")
    if aa == "operator_defined" or aa is None:
        allowed: Optional[List[str]] = None
    else:
        allowed = list(aa)

    return {
        "allowed_adapters": allowed,
        "forbidden_adapters": list(profile.get("forbidden_adapters") or []),
        "forbidden_effects": list(profile.get("forbidden_effects") or []),
        "forbidden_effect_tiers": list(profile.get("forbidden_effect_tiers") or []),
        "forbidden_privilege_tiers": list(profile.get("forbidden_privilege_tiers") or []),
        "limits": dict(profile.get("runtime_limits") or {}),
        "adapter_constraints": {},
    }


__all__ = [
    "empty_grant",
    "env_truthy",
    "merge_grants",
    "grant_to_policy",
    "grant_to_limits",
    "grant_to_allowed_adapters",
    "load_profile_as_grant",
]
