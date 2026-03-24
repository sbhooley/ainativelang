"""
Tests for the /capabilities endpoints on the runner service.

Covers:
- /capabilities returns 200 with expected schema (schema_version 1.1)
- response includes runtime_version, adapters, policy_support
- adapter entries include verbs, support_tier, effect_default
- core adapters are present
- response is stable across repeated calls (cached)
- /capabilities/langgraph and /capabilities/temporal static emitter descriptors
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.runtime_runner_service import app, _CAPABILITIES_CACHE

client = TestClient(app)


def test_capabilities_returns_200():
    resp = client.get("/capabilities")
    assert resp.status_code == 200


def test_capabilities_has_required_fields():
    body = client.get("/capabilities").json()
    assert "schema_version" in body
    assert "runtime_version" in body
    assert "adapters" in body
    assert "policy_support" in body
    assert body["schema_version"] == "1.1"
    assert isinstance(body["runtime_version"], str)
    assert body["policy_support"] is True


def test_capabilities_includes_core_adapters():
    adapters = client.get("/capabilities").json()["adapters"]
    for name in ("core", "http", "sqlite", "fs", "tools", "cache", "queue"):
        assert name in adapters, f"missing core adapter: {name}"
        assert adapters[name]["support_tier"] == "core"


def test_capabilities_adapter_entries_have_expected_shape():
    adapters = client.get("/capabilities").json()["adapters"]
    for name, info in adapters.items():
        assert "support_tier" in info, f"{name} missing support_tier"
        assert "verbs" in info, f"{name} missing verbs"
        assert isinstance(info["verbs"], list), f"{name} verbs is not a list"
        assert "effect_default" in info, f"{name} missing effect_default"
        assert "recommended_lane" in info, f"{name} missing recommended_lane"
        # privilege_tier is optional but should be present for known adapters.
        assert "privilege_tier" in info, f"{name} missing privilege_tier"


def test_capabilities_includes_extension_adapters():
    adapters = client.get("/capabilities").json()["adapters"]
    for name in ("memory", "agent", "svc"):
        assert name in adapters, f"missing extension adapter: {name}"
        assert adapters[name]["support_tier"] == "extension_openclaw"


def test_capabilities_core_adapter_has_verbs():
    adapters = client.get("/capabilities").json()["adapters"]
    core_verbs = adapters["core"]["verbs"]
    assert "ADD" in core_verbs
    assert "CONCAT" in core_verbs
    assert len(core_verbs) > 5


def test_capabilities_is_stable():
    a = client.get("/capabilities").json()
    b = client.get("/capabilities").json()
    assert a == b


def test_capabilities_langgraph_returns_200():
    resp = client.get("/capabilities/langgraph")
    assert resp.status_code == 200
    body = resp.json()
    assert body["emitter"] == "langgraph"
    assert body["schema_version"] == "1.0"
    assert "cli_example_strict" in body
    assert "LangGraph" in body["summary"]


def test_capabilities_temporal_returns_200():
    resp = client.get("/capabilities/temporal")
    assert resp.status_code == 200
    body = resp.json()
    assert body["emitter"] == "temporal"
    assert body["schema_version"] == "1.0"
    assert "cli_example_strict" in body
    assert "Temporal" in body["summary"]
