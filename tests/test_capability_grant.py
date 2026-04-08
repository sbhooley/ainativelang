import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.capability_grant import (
    empty_grant,
    env_truthy,
    merge_grants,
    grant_to_policy,
    grant_to_limits,
    grant_to_allowed_adapters,
    load_profile_as_grant,
)


def test_empty_grant_is_maximally_permissive():
    g = empty_grant()
    assert g["allowed_adapters"] is None
    assert g["forbidden_adapters"] == []
    assert g["limits"] == {}


def _grant(**overrides):
    """Build a grant dict with sensible empty defaults, overridable by kwargs."""
    base = {
        "allowed_adapters": None,
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": {},
        "adapter_constraints": {},
    }
    base.update(overrides)
    return base


def test_merge_allowed_adapters_intersection():
    base = _grant(allowed_adapters=["core", "http", "fs"])
    overlay = _grant(allowed_adapters=["core", "sqlite"])
    m = merge_grants(base, overlay)
    assert m["allowed_adapters"] == ["core"]


def test_merge_allowed_adapters_none_defers():
    base = _grant(allowed_adapters=None)
    overlay = _grant(allowed_adapters=["core", "http"])
    m = merge_grants(base, overlay)
    assert m["allowed_adapters"] == ["core", "http"]


def test_merge_forbidden_sets_union():
    base = _grant(forbidden_adapters=["http"])
    overlay = _grant(forbidden_adapters=["fs"])
    m = merge_grants(base, overlay)
    assert set(m["forbidden_adapters"]) == {"http", "fs"}


def test_merge_forbidden_privilege_tiers_union():
    base = _grant(forbidden_privilege_tiers=["network"])
    overlay = _grant(forbidden_privilege_tiers=["operator_sensitive"])
    m = merge_grants(base, overlay)
    assert set(m["forbidden_privilege_tiers"]) == {"network", "operator_sensitive"}


def test_merge_limits_takes_minimum():
    base = _grant(limits={"max_steps": 1000, "max_depth": 20})
    overlay = _grant(limits={"max_steps": 500, "max_time_ms": 3000})
    m = merge_grants(base, overlay)
    assert m["limits"]["max_steps"] == 500
    assert m["limits"]["max_depth"] == 20
    assert m["limits"]["max_time_ms"] == 3000


def test_merge_limits_caller_cannot_widen():
    server = _grant(limits={"max_steps": 500})
    caller = _grant(limits={"max_steps": 9999})
    m = merge_grants(server, caller)
    assert m["limits"]["max_steps"] == 500


def test_merge_adapter_constraints_intersection():
    base = _grant(adapter_constraints={"http": {"allow_hosts": ["a.com", "b.com"]}})
    overlay = _grant(adapter_constraints={"http": {"allow_hosts": ["b.com", "c.com"]}})
    m = merge_grants(base, overlay)
    assert m["adapter_constraints"]["http"]["allow_hosts"] == ["b.com"]


def test_grant_to_policy_extracts_forbidden_sets():
    g = empty_grant()
    g["forbidden_adapters"] = ["http"]
    g["forbidden_privilege_tiers"] = ["network"]
    p = grant_to_policy(g)
    assert p == {"forbidden_adapters": ["http"], "forbidden_privilege_tiers": ["network"]}


def test_grant_to_limits_extracts_limits():
    g = empty_grant()
    g["limits"] = {"max_steps": 100}
    assert grant_to_limits(g) == {"max_steps": 100}


def test_grant_to_allowed_adapters_with_fallback():
    g = empty_grant()
    assert grant_to_allowed_adapters(g) is None
    assert grant_to_allowed_adapters(g, fallback=["core", "http"]) == ["core", "http"]
    g["allowed_adapters"] = ["sqlite"]
    assert grant_to_allowed_adapters(g) == ["sqlite"]


def test_load_profile_as_grant_local_minimal():
    g = load_profile_as_grant("local_minimal")
    assert g["allowed_adapters"] == ["core"]
    assert "network" in g["forbidden_privilege_tiers"]
    assert g["limits"]["max_steps"] == 500


def test_load_profile_as_grant_operator_full():
    g = load_profile_as_grant("operator_full")
    assert g["allowed_adapters"] is None
    assert g["forbidden_privilege_tiers"] == []


def test_env_truthy():
    assert env_truthy("1") is True
    assert env_truthy("true") is True
    assert env_truthy("") is False
    assert env_truthy(None) is False


def test_load_profile_consumer_secure_default_includes_web():
    g = load_profile_as_grant("consumer_secure_default")
    aa = grant_to_allowed_adapters(g)
    assert aa is not None
    assert "web" in aa
    assert "llm" in aa
    assert "operator_sensitive" in g["forbidden_privilege_tiers"]


def test_load_profile_unknown_raises():
    try:
        load_profile_as_grant("nonexistent_profile")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_merge_is_commutatively_restrictive():
    """Merging A+B and B+A should both be at least as restrictive as either."""
    a = _grant(
        allowed_adapters=["core", "http"],
        forbidden_adapters=["agent"],
        limits={"max_steps": 1000},
    )
    b = _grant(
        allowed_adapters=["core", "fs"],
        forbidden_adapters=["svc"],
        limits={"max_steps": 500},
    )
    ab = merge_grants(a, b)
    ba = merge_grants(b, a)
    assert ab["allowed_adapters"] == ba["allowed_adapters"] == ["core"]
    assert set(ab["forbidden_adapters"]) == set(ba["forbidden_adapters"]) == {"agent", "svc"}
    assert ab["limits"]["max_steps"] == ba["limits"]["max_steps"] == 500
