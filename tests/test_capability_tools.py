import json
from pathlib import Path

import pytest

from scripts.capabilities_report import build_report
from scripts.capabilities_filter import filter_tools, list_values


ROOT = Path(__file__).resolve().parent.parent


def _load_json(rel: str):
  return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_capability_report_counts_align_with_registry():
  caps = _load_json("tooling/capabilities.json")
  report = build_report()

  # Kinds from tools descriptor should reflect adapter_verbs + module_skills.
  total_adapter_verbs = len(caps.get("adapter_verbs", []))
  total_module_skills = len(caps.get("module_skills", []))

  by_kind = report["by_kind"]
  assert by_kind.get("adapter_verb", 0) == total_adapter_verbs
  assert by_kind.get("module_skill", 0) == total_module_skills

  # Domain counts should at least mention some known domains.
  by_domain = report["by_domain"]
  assert "http" in by_domain
  assert "memory" in by_domain

  by_usage = report["by_usage_model"]
  # All adapter_verbs should be primitive and all module_skills composite.
  assert by_usage.get("primitive", 0) == len(caps.get("adapter_verbs", []))
  assert by_usage.get("composite", 0) == len(caps.get("module_skills", []))


def test_filter_canonical_adapter_verbs():
  tools = filter_tools(kind="adapter_verb", lane="canonical")
  assert tools, "expected at least one canonical adapter_verb"
  for t in tools:
    assert t["kind"] == "adapter_verb"
    assert t["lane"] == "canonical"


def test_filter_extension_operator_only():
  tools = filter_tools(
    kind="adapter_verb",
    support_tier="extension_openclaw",
    has_safety_tags=["operator_only"],
  )
  # We expect at least one such tool in the current registry (e.g. memory.prune or svc.caddy).
  assert tools, "expected at least one extension_openclaw operator_only tool"
  for t in tools:
    assert t["kind"] == "adapter_verb"
    assert t["support_tier"] == "extension_openclaw"
    assert "operator_only" in (t.get("safety_tags") or [])


def test_filter_module_skills_only():
  tools = filter_tools(kind="module_skill")
  assert tools, "expected module_skill tools"
  for t in tools:
    assert t["kind"] == "module_skill"


def test_filter_by_domain_http():
  tools = filter_tools(kind="adapter_verb", domain="http")
  assert tools, "expected at least one http-domain tool"
  for t in tools:
    assert t["kind"] == "adapter_verb"
    assert t.get("domain") == "http"


def test_filter_by_usage_model_composite():
  tools = filter_tools(usage_model="composite")
  assert tools, "expected at least one composite tool (module_skill)"
  for t in tools:
    assert t.get("usage_model") == "composite"


def test_filter_by_common_pattern_key_value_write():
  tools = filter_tools(common_pattern="key-value write")
  assert tools, "expected at least one key-value write tool"
  ids = {t["id"] for t in tools}
  assert "adapter.memory.put" in ids


def test_list_values_domain_includes_expected_domains():
  vals = set(list_values("domain"))
  assert {"http", "memory", "coordination"}.issubset(vals)


def test_list_values_usage_model_primitive_and_composite():
  vals = set(list_values("usage_model"))
  assert vals == {"primitive", "composite"}


def test_list_values_safety_tags_includes_known_tags():
  vals = set(list_values("safety_tags"))
  for tag in ["safe_default", "operator_only"]:
    assert tag in vals


def test_list_values_unsupported_field_raises():
  with pytest.raises(ValueError):
    list_values("nonexistent_field")


def test_capabilities_filter_cli_basic_invocations(tmp_path):
  """Smoke-test the CLI script for common commands."""
  import subprocess
  import sys
  from pathlib import Path as _Path

  root = _Path(__file__).resolve().parent.parent
  script = root / "scripts" / "capabilities_filter.py"

  cmds = [
    [sys.executable, str(script), "--domain", "memory"],
    [sys.executable, str(script), "--usage-model", "composite", "--json"],
    [sys.executable, str(script), "--list-values", "domain"],
  ]

  for cmd in cmds:
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert proc.returncode == 0, f"Command failed: {cmd} stderr={proc.stderr}"
    # Expect some non-empty stdout for discovery/usability.
    assert proc.stdout.strip(), f"Command produced empty output: {cmd}"

