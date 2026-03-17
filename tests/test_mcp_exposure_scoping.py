"""Tests for MCP tool/resource exposure scoping.

Validates that the AINL MCP server correctly restricts which tools and
resources are registered based on environment variables and named exposure
profiles.  These tests exercise the scoping logic directly without
requiring the MCP SDK transport.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers — re-import scoping internals after env manipulation
# ---------------------------------------------------------------------------

def _reimport_scoping(env_overrides: Dict[str, str] | None = None):
    """Re-execute exposure resolution under a patched environment.

    Returns (allowed_tools, allowed_resources) as sets.
    """
    env = dict(os.environ)
    for key in (
        "AINL_MCP_TOOLS", "AINL_MCP_TOOLS_EXCLUDE",
        "AINL_MCP_RESOURCES", "AINL_MCP_RESOURCES_EXCLUDE",
        "AINL_MCP_EXPOSURE_PROFILE",
    ):
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)
    with mock.patch.dict(os.environ, env, clear=True):
        from scripts.ainl_mcp_server import _resolve_exposure
        return _resolve_exposure()


# ---------------------------------------------------------------------------
# Default behaviour
# ---------------------------------------------------------------------------

class TestDefaultExposure:
    def test_all_tools_exposed_by_default(self):
        tools, _ = _reimport_scoping()
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES
        assert tools == set(ALL_TOOL_NAMES)

    def test_all_resources_exposed_by_default(self):
        _, resources = _reimport_scoping()
        from scripts.ainl_mcp_server import ALL_RESOURCE_URIS
        assert resources == set(ALL_RESOURCE_URIS)


# ---------------------------------------------------------------------------
# Env-var inclusion
# ---------------------------------------------------------------------------

class TestEnvInclusion:
    def test_tools_inclusion_restricts(self):
        tools, _ = _reimport_scoping({"AINL_MCP_TOOLS": "ainl_validate,ainl_compile"})
        assert tools == {"ainl_validate", "ainl_compile"}

    def test_resources_inclusion_restricts(self):
        _, resources = _reimport_scoping({"AINL_MCP_RESOURCES": "ainl://adapter-manifest"})
        assert resources == {"ainl://adapter-manifest"}

    def test_tools_inclusion_unknown_name_ignored(self):
        tools, _ = _reimport_scoping({"AINL_MCP_TOOLS": "ainl_validate,nonexistent_tool"})
        assert tools == {"ainl_validate"}

    def test_empty_inclusion_results_in_empty_set(self):
        tools, _ = _reimport_scoping({"AINL_MCP_TOOLS": ""})
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES
        assert tools == set(ALL_TOOL_NAMES), "empty string should behave as unset"


# ---------------------------------------------------------------------------
# Env-var exclusion
# ---------------------------------------------------------------------------

class TestEnvExclusion:
    def test_tools_exclusion_removes(self):
        tools, _ = _reimport_scoping({"AINL_MCP_TOOLS_EXCLUDE": "ainl_run"})
        assert "ainl_run" not in tools
        assert "ainl_validate" in tools

    def test_resources_exclusion_removes(self):
        _, resources = _reimport_scoping({"AINL_MCP_RESOURCES_EXCLUDE": "ainl://security-profiles"})
        assert "ainl://security-profiles" not in resources
        assert "ainl://adapter-manifest" in resources

    def test_inclusion_and_exclusion_combined(self):
        tools, _ = _reimport_scoping({
            "AINL_MCP_TOOLS": "ainl_validate,ainl_compile,ainl_run",
            "AINL_MCP_TOOLS_EXCLUDE": "ainl_run",
        })
        assert tools == {"ainl_validate", "ainl_compile"}


# ---------------------------------------------------------------------------
# Named exposure profiles
# ---------------------------------------------------------------------------

class TestExposureProfiles:
    def test_validate_only_profile(self):
        tools, resources = _reimport_scoping({"AINL_MCP_EXPOSURE_PROFILE": "validate_only"})
        assert tools == {"ainl_validate", "ainl_compile"}
        assert resources == set()

    def test_inspect_only_profile(self):
        tools, resources = _reimport_scoping({"AINL_MCP_EXPOSURE_PROFILE": "inspect_only"})
        assert tools == {"ainl_validate", "ainl_compile", "ainl_capabilities", "ainl_security_report"}
        assert "ainl_run" not in tools
        assert "ainl://adapter-manifest" in resources

    def test_safe_workflow_profile(self):
        tools, resources = _reimport_scoping({"AINL_MCP_EXPOSURE_PROFILE": "safe_workflow"})
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES, ALL_RESOURCE_URIS
        assert tools == set(ALL_TOOL_NAMES)
        assert resources == set(ALL_RESOURCE_URIS)

    def test_full_profile(self):
        tools, resources = _reimport_scoping({"AINL_MCP_EXPOSURE_PROFILE": "full"})
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES, ALL_RESOURCE_URIS
        assert tools == set(ALL_TOOL_NAMES)
        assert resources == set(ALL_RESOURCE_URIS)

    def test_unknown_profile_ignored(self):
        tools, resources = _reimport_scoping({"AINL_MCP_EXPOSURE_PROFILE": "nonexistent_profile"})
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES, ALL_RESOURCE_URIS
        assert tools == set(ALL_TOOL_NAMES)
        assert resources == set(ALL_RESOURCE_URIS)


# ---------------------------------------------------------------------------
# Profile + env-var composition
# ---------------------------------------------------------------------------

class TestProfileEnvComposition:
    def test_profile_then_env_narrows_further(self):
        """Env inclusion intersects with profile."""
        tools, _ = _reimport_scoping({
            "AINL_MCP_EXPOSURE_PROFILE": "inspect_only",
            "AINL_MCP_TOOLS": "ainl_validate",
        })
        assert tools == {"ainl_validate"}

    def test_profile_then_env_exclude_narrows_further(self):
        tools, _ = _reimport_scoping({
            "AINL_MCP_EXPOSURE_PROFILE": "safe_workflow",
            "AINL_MCP_TOOLS_EXCLUDE": "ainl_run",
        })
        assert "ainl_run" not in tools
        assert "ainl_validate" in tools


# ---------------------------------------------------------------------------
# Exposure profiles file shape
# ---------------------------------------------------------------------------

class TestExposureProfileFile:
    def test_profiles_file_shape(self):
        path = ROOT / "tooling" / "mcp_exposure_profiles.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "profiles" in data
        assert "schema_version" in data
        for name, profile in data["profiles"].items():
            assert "tools" in profile, f"profile {name} missing 'tools'"
            assert "resources" in profile, f"profile {name} missing 'resources'"
            assert isinstance(profile["tools"], list)
            assert isinstance(profile["resources"], list)

    def test_all_profile_tools_are_valid(self):
        from scripts.ainl_mcp_server import ALL_TOOL_NAMES
        path = ROOT / "tooling" / "mcp_exposure_profiles.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        valid = set(ALL_TOOL_NAMES)
        for name, profile in data["profiles"].items():
            for t in profile["tools"]:
                assert t in valid, f"profile {name} references unknown tool {t}"

    def test_all_profile_resources_are_valid(self):
        from scripts.ainl_mcp_server import ALL_RESOURCE_URIS
        path = ROOT / "tooling" / "mcp_exposure_profiles.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        valid = set(ALL_RESOURCE_URIS)
        for name, profile in data["profiles"].items():
            for r in profile["resources"]:
                assert r in valid, f"profile {name} references unknown resource {r}"


# ---------------------------------------------------------------------------
# Scoping does NOT affect execution authorization
# ---------------------------------------------------------------------------

class TestScopingVsAuthorization:
    """Exposure scoping controls discovery; it does not relax security."""

    def test_scoped_run_still_enforces_policy(self):
        """Even when ainl_run is exposed, policy still restricts execution."""
        from scripts.ainl_mcp_server import ainl_run
        result = ainl_run(
            "S app api /api\nL1:\nR http.Get \"https://example.com\" ->resp\nJ resp",
            strict=True,
        )
        assert result["ok"] is False
        assert result.get("error") == "policy_violation"
