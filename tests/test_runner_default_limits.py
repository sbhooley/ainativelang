"""Tests proving that server-default limits are enforced and callers cannot widen."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.runtime_runner_service as _runner_mod
from scripts.runtime_runner_service import (
    _run_guarded,
    PolicyViolationError,
    _SERVER_DEFAULT_LIMITS,
)
from tooling.capability_grant import merge_grants, empty_grant
import uuid


def _trace_id():
    return str(uuid.uuid4())


def _reset_server_grant(**overrides):
    """Build a controlled server grant for tests."""
    base = {
        "allowed_adapters": ["core"],
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": dict(_SERVER_DEFAULT_LIMITS),
        "adapter_constraints": {},
    }
    base.update(overrides)
    return base


class TestDefaultLimitsEnforced:
    def setup_method(self):
        self._old_grant = _runner_mod._SERVER_GRANT
        _runner_mod._SERVER_GRANT = _reset_server_grant()

    def teardown_method(self):
        _runner_mod._SERVER_GRANT = self._old_grant

    def test_server_defaults_apply_when_caller_omits_limits(self):
        """If the caller sends no limits, server defaults are used."""
        req = {"code": "L1: Set a 1 J a\n"}
        result = _run_guarded(req, _trace_id())
        assert result["ok"] is True

    def test_caller_can_tighten_limits(self):
        req = {
            "code": "L1: Set a 1 Set b 2 Set c 3 J c\n",
            "limits": {"max_steps": 1},
        }
        result = _run_guarded(req, _trace_id())
        assert result["ok"] is False
        assert "max_steps" in str(result.get("error", ""))

    def test_caller_cannot_widen_max_steps_beyond_server(self):
        _runner_mod._SERVER_GRANT = _reset_server_grant(limits={"max_steps": 3})
        req = {
            "code": "L1: Set a 1 Set b 2 Set c 3 Set d 4 Set e 5 J e\n",
            "limits": {"max_steps": 99999},
        }
        result = _run_guarded(req, _trace_id())
        assert result["ok"] is False
        assert "max_steps" in str(result.get("error", ""))

    def test_caller_cannot_widen_allowed_adapters(self):
        _runner_mod._SERVER_GRANT = _reset_server_grant(allowed_adapters=["core"])
        req = {
            "code": "L1: R ext.echo 1 ->x J x\n",
            "allowed_adapters": ["core", "ext"],
            "adapters": {"enable": ["ext"]},
        }
        result = _run_guarded(req, _trace_id())
        assert result["ok"] is False
        assert "blocked" in str(result.get("error", "")).lower() or \
               "ext" in str(result.get("error", "")).lower()

    def test_server_grant_forbidden_tiers_enforced(self):
        _runner_mod._SERVER_GRANT = _reset_server_grant(
            forbidden_privilege_tiers=["network"],
        )
        req = {"code": "L1: R http.Get example.com ->x J x\n"}
        try:
            result = _run_guarded(req, _trace_id())
            assert result["ok"] is False
        except PolicyViolationError:
            pass  # also acceptable — policy violation raised before guarded wrap


class TestMcpDefaultsAtLeastAsStrictAsRunner:
    def test_mcp_max_steps_leq_runner(self):
        from scripts.ainl_mcp_server import _DEFAULT_LIMITS, _MCP_SERVER_GRANT
        runner_steps = _SERVER_DEFAULT_LIMITS.get("max_steps", float("inf"))
        mcp_steps = _DEFAULT_LIMITS.get("max_steps", float("inf"))
        assert mcp_steps <= runner_steps

    def test_mcp_max_adapter_calls_leq_runner(self):
        from scripts.ainl_mcp_server import _DEFAULT_LIMITS
        runner_val = _SERVER_DEFAULT_LIMITS.get("max_adapter_calls", float("inf"))
        mcp_val = _DEFAULT_LIMITS.get("max_adapter_calls", float("inf"))
        assert mcp_val <= runner_val


class TestGrantMergePropertiesForLimits:
    def test_merge_min_semantics(self):
        server = {"limits": {"max_steps": 2000, "max_time_ms": 30000},
                  **_stub_grant()}
        caller = {"limits": {"max_steps": 500, "max_time_ms": 60000},
                  **_stub_grant()}
        effective = merge_grants(server, caller)
        assert effective["limits"]["max_steps"] == 500
        assert effective["limits"]["max_time_ms"] == 30000

    def test_empty_caller_limits_preserves_server(self):
        server = {"limits": {"max_steps": 2000}, **_stub_grant()}
        caller = {"limits": {}, **_stub_grant()}
        effective = merge_grants(server, caller)
        assert effective["limits"]["max_steps"] == 2000


def _stub_grant():
    return {
        "allowed_adapters": None,
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "adapter_constraints": {},
    }
