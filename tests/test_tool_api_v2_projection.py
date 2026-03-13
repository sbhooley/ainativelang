import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_json(rel: str):
  return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_tool_api_v2_includes_adapter_verbs_and_module_skills():
  tools_doc = _load_json("tooling/tool_api_v2.tools.json")
  tools = tools_doc["tools"]

  kinds = {t["kind"] for t in tools}
  assert "adapter_verb" in kinds
  assert "module_skill" in kinds


def test_tool_api_v2_module_skill_ids_match_registry():
  tools_doc = _load_json("tooling/tool_api_v2.tools.json")
  caps_doc = _load_json("tooling/capabilities.json")

  tool_ids = {t["id"] for t in tools_doc["tools"] if t["kind"] == "module_skill"}
  cap_ids = {m["id"] for m in caps_doc["module_skills"]}

  # Tool API v2 must expose all registered module skills.
  assert tool_ids == cap_ids


def test_tool_api_v2_adapter_verb_ids_match_registry_subset():
  tools_doc = _load_json("tooling/tool_api_v2.tools.json")
  caps_doc = _load_json("tooling/capabilities.json")

  tool_ids = {t["id"] for t in tools_doc["tools"] if t["kind"] == "adapter_verb"}
  cap_ids = {av["id"] for av in caps_doc["adapter_verbs"]}

  # Tool API v2 must expose all registered adapter_verbs (current subset).
  assert tool_ids == cap_ids


def test_tool_api_v2_module_skill_shape_is_descriptive_only():
  tools_doc = _load_json("tooling/tool_api_v2.tools.json")
  ms = {t["id"]: t for t in tools_doc["tools"] if t["kind"] == "module_skill"}

  assert "module.examples.hello" in ms
  assert "module.openclaw.monitor_status_advice" in ms

  hello = ms["module.examples.hello"]
  advice = ms["module.openclaw.monitor_status_advice"]

  for entry in (hello, advice):
    assert "name" in entry
    assert "description" in entry
    assert "source" in entry and "program_path" in entry["source"]
    assert isinstance(entry.get("inputs"), list)
    assert isinstance(entry.get("outputs"), list)
    assert isinstance(entry.get("effects"), list)
    assert isinstance(entry.get("adapter_dependencies"), list)
    assert isinstance(entry.get("safety_tags"), list)
    assert isinstance(entry.get("lane"), str)
    assert isinstance(entry.get("support_tier"), str)
    assert isinstance(entry.get("domain"), str)
    assert entry.get("usage_model") == "composite"
    assert isinstance(entry.get("common_pattern"), str)


