"""Tests for security profile → grant integration across runner and MCP."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.capability_grant import (
    load_profile_as_grant,
    merge_grants,
    grant_to_policy,
    grant_to_limits,
    grant_to_allowed_adapters,
)


class TestProfileToGrant:
    def test_local_minimal_grant_restricts_correctly(self):
        g = load_profile_as_grant("local_minimal")
        assert g["allowed_adapters"] == ["core"]
        assert "network" in g["forbidden_privilege_tiers"]
        assert "local_state" in g["forbidden_privilege_tiers"]
        assert "operator_sensitive" in g["forbidden_privilege_tiers"]
        assert g["limits"]["max_steps"] == 500
        assert g["limits"]["max_adapter_calls"] == 0

    def test_sandbox_compute_and_store_grant(self):
        g = load_profile_as_grant("sandbox_compute_and_store")
        aa = set(g["allowed_adapters"])
        assert "core" in aa
        assert "sqlite" in aa
        assert "http" not in aa
        assert "network" in g["forbidden_privilege_tiers"]
        assert g["limits"]["max_steps"] == 5000

    def test_sandbox_network_restricted_grant(self):
        g = load_profile_as_grant("sandbox_network_restricted")
        aa = set(g["allowed_adapters"])
        assert "http" in aa
        assert "core" in aa
        assert "agent" not in g.get("allowed_adapters", [])
        assert "operator_sensitive" in g["forbidden_privilege_tiers"]

    def test_operator_full_grant_is_maximally_permissive(self):
        g = load_profile_as_grant("operator_full")
        assert g["allowed_adapters"] is None
        assert g["forbidden_adapters"] == []
        assert g["forbidden_privilege_tiers"] == []
        assert g["limits"]["max_steps"] == 50000


class TestProfileMergedWithCallerGrant:
    def test_caller_cannot_widen_local_minimal(self):
        server = load_profile_as_grant("local_minimal")
        caller = {
            "allowed_adapters": ["core", "http", "sqlite"],
            "forbidden_adapters": [],
            "forbidden_effects": [],
            "forbidden_effect_tiers": [],
            "forbidden_privilege_tiers": [],
            "limits": {"max_steps": 99999},
            "adapter_constraints": {},
        }
        effective = merge_grants(server, caller)
        assert effective["allowed_adapters"] == ["core"]
        assert effective["limits"]["max_steps"] == 500

    def test_caller_can_tighten_sandbox_compute(self):
        server = load_profile_as_grant("sandbox_compute_and_store")
        caller = {
            "allowed_adapters": ["core"],
            "forbidden_adapters": [],
            "forbidden_effects": [],
            "forbidden_effect_tiers": [],
            "forbidden_privilege_tiers": [],
            "limits": {"max_steps": 100},
            "adapter_constraints": {},
        }
        effective = merge_grants(server, caller)
        assert effective["allowed_adapters"] == ["core"]
        assert effective["limits"]["max_steps"] == 100

    def test_caller_forbidden_tiers_union_with_profile(self):
        server = load_profile_as_grant("sandbox_network_restricted")
        caller = {
            "allowed_adapters": None,
            "forbidden_adapters": [],
            "forbidden_effects": [],
            "forbidden_effect_tiers": [],
            "forbidden_privilege_tiers": ["local_state"],
            "limits": {},
            "adapter_constraints": {},
        }
        effective = merge_grants(server, caller)
        assert "operator_sensitive" in effective["forbidden_privilege_tiers"]
        assert "local_state" in effective["forbidden_privilege_tiers"]


class TestProfileGrantExtraction:
    def test_grant_to_policy_from_profile(self):
        g = load_profile_as_grant("local_minimal")
        p = grant_to_policy(g)
        assert "forbidden_privilege_tiers" in p
        assert "network" in p["forbidden_privilege_tiers"]

    def test_grant_to_limits_from_profile(self):
        g = load_profile_as_grant("sandbox_compute_and_store")
        lim = grant_to_limits(g)
        assert lim["max_steps"] == 5000
        assert lim["max_depth"] == 50

    def test_grant_to_allowed_adapters_from_profile(self):
        g = load_profile_as_grant("sandbox_compute_and_store")
        aa = grant_to_allowed_adapters(g)
        assert "core" in aa
        assert "sqlite" in aa


class TestRunnerProfileEnvVar:
    def test_runner_loads_profile_from_env(self):
        import scripts.runtime_runner_service as _runner_mod
        old = _runner_mod._SERVER_GRANT
        try:
            os.environ["AINL_SECURITY_PROFILE"] = "sandbox_compute_and_store"
            new_grant = _runner_mod._load_server_grant()
            assert "core" in new_grant["allowed_adapters"]
            assert "sqlite" in new_grant["allowed_adapters"]
            assert "network" in new_grant["forbidden_privilege_tiers"]
        finally:
            os.environ.pop("AINL_SECURITY_PROFILE", None)
            _runner_mod._SERVER_GRANT = old

    def test_runner_falls_back_on_unknown_profile(self):
        import scripts.runtime_runner_service as _runner_mod
        old = _runner_mod._SERVER_GRANT
        try:
            os.environ["AINL_SECURITY_PROFILE"] = "nonexistent_fake"
            new_grant = _runner_mod._load_server_grant()
            assert new_grant["allowed_adapters"] == ["core"]
        finally:
            os.environ.pop("AINL_SECURITY_PROFILE", None)
            _runner_mod._SERVER_GRANT = old


class TestMcpProfileEnvVar:
    def test_mcp_loads_profile_from_env(self):
        old_val = os.environ.get("AINL_MCP_PROFILE")
        try:
            os.environ["AINL_MCP_PROFILE"] = "sandbox_compute_and_store"
            from scripts.ainl_mcp_server import _load_mcp_server_grant
            new_grant = _load_mcp_server_grant()
            assert "core" in new_grant["allowed_adapters"]
            assert "sqlite" in new_grant["allowed_adapters"]
        finally:
            if old_val is None:
                os.environ.pop("AINL_MCP_PROFILE", None)
            else:
                os.environ["AINL_MCP_PROFILE"] = old_val
