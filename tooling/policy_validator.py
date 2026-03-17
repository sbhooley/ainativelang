"""
Policy validation over AINL IR.

This module enforces simple, declarative policies on compiled IR, such as:
- Forbid certain adapters (e.g. no network/http in this workspace).
- Forbid certain effect tiers (e.g. no io-write).

It is intentionally small and machine-friendly for use by agents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tooling.adapter_manifest import ADAPTER_MANIFEST  # type: ignore
from tooling.graph_api import label_nodes


def _node_adapter_name(node: Dict[str, Any]) -> Optional[str]:
    data = node.get("data") or {}
    adapter = data.get("adapter") or ""
    if not adapter:
        return None
    # adapter form: "db.F", "http.Get", "cache.Get", etc.
    return str(adapter).split(".")[0]


def _adapter_privilege_tier(adapter_name: str) -> Optional[str]:
    """Lookup privilege_tier for the adapter name from adapter metadata."""
    info = (ADAPTER_MANIFEST.get("adapters") or {}).get(adapter_name) or {}
    tier = info.get("privilege_tier")
    if isinstance(tier, str) and tier:
        return tier
    return None


def _adapter_is_destructive(adapter_name: str) -> bool:
    """Check if the adapter is marked as destructive in metadata."""
    info = (ADAPTER_MANIFEST.get("adapters") or {}).get(adapter_name) or {}
    return bool(info.get("destructive"))


def validate_ir_against_policy(ir: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate IR against a simple policy.

    Policy fields (all optional):
      - forbidden_adapters: [name, ...]
      - forbidden_effects: [effect, ...]
      - forbidden_effect_tiers: [tier, ...]
      - forbidden_privilege_tiers: [tier, ...]

    Returns:
      {"ok": True} on success
      {"ok": False, "errors": [ {code, message, data}, ... ]} on violation
    """
    labels = ir.get("labels") or {}
    forbidden_adapters = set(policy.get("forbidden_adapters") or [])
    forbidden_effects = set(policy.get("forbidden_effects") or [])
    forbidden_tiers = set(policy.get("forbidden_effect_tiers") or [])
    forbidden_priv_tiers = set(policy.get("forbidden_privilege_tiers") or [])
    forbid_destructive = bool(policy.get("forbidden_destructive"))

    errors: List[Dict[str, Any]] = []

    for lid in sorted(labels.keys(), key=str):
        nodes = label_nodes(ir, lid)
        for nid, node in nodes.items():
            adapter_name = _node_adapter_name(node)
            if adapter_name and adapter_name in forbidden_adapters:
                errors.append(
                    {
                        "code": "POLICY_ADAPTER_FORBIDDEN",
                        "message": f"Adapter {adapter_name!r} is forbidden by policy",
                        "data": {"label_id": str(lid), "node_id": nid, "adapter": adapter_name},
                    }
                )
            eff = node.get("effect")
            if eff and eff in forbidden_effects:
                errors.append(
                    {
                        "code": "POLICY_EFFECT_FORBIDDEN",
                        "message": f"Effect {eff!r} is forbidden by policy",
                        "data": {"label_id": str(lid), "node_id": nid, "effect": eff},
                    }
                )
            tier = node.get("effect_tier")
            if tier and tier in forbidden_tiers:
                errors.append(
                    {
                        "code": "POLICY_TIER_FORBIDDEN",
                        "message": f"Effect tier {tier!r} is forbidden by policy",
                        "data": {"label_id": str(lid), "node_id": nid, "effect_tier": tier},
                    }
                )
            if adapter_name and forbidden_priv_tiers:
                priv = _adapter_privilege_tier(adapter_name)
                if priv and priv in forbidden_priv_tiers:
                    errors.append(
                        {
                            "code": "POLICY_PRIVILEGE_TIER_FORBIDDEN",
                            "message": f"Privilege tier {priv!r} is forbidden by policy",
                            "data": {"label_id": str(lid), "node_id": nid, "adapter": adapter_name, "privilege_tier": priv},
                        }
                    )
            if adapter_name and forbid_destructive and _adapter_is_destructive(adapter_name):
                errors.append(
                    {
                        "code": "POLICY_DESTRUCTIVE_FORBIDDEN",
                        "message": f"Destructive adapter {adapter_name!r} is forbidden by policy",
                        "data": {"label_id": str(lid), "node_id": nid, "adapter": adapter_name},
                    }
                )

    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True}


__all__ = ["validate_ir_against_policy"]

