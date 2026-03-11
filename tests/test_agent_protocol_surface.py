import json
import os
import re
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_manifest():
  root = os.path.dirname(os.path.dirname(__file__))
  p = os.path.join(root, "tooling", "adapter_manifest.json")
  with open(p, "r", encoding="utf-8") as f:
    return json.load(f)


def _load_registry():
  root = os.path.dirname(os.path.dirname(__file__))
  p = os.path.join(root, "ADAPTER_REGISTRY.json")
  with open(p, "r", encoding="utf-8") as f:
    return json.load(f)


def _load_docs_adapter_registry() -> str:
  root = os.path.dirname(os.path.dirname(__file__))
  p = os.path.join(root, "docs", "ADAPTER_REGISTRY.md")
  with open(p, "r", encoding="utf-8") as f:
    return f.read()


AGENT_SHARED_VERBS = {"send_task", "read_result"}


def test_agent_manifest_verbs_locked_to_shared_surface():
  m = _load_manifest()
  adapters = m.get("adapters", {})
  agent = adapters.get("agent") or {}
  verbs = set(agent.get("verbs") or [])
  assert verbs == AGENT_SHARED_VERBS, (
      f"agent manifest verbs {sorted(verbs)} do not match shared "
      f"protocol surface {sorted(AGENT_SHARED_VERBS)}"
  )


def test_agent_registry_verbs_locked_to_shared_surface():
  r = _load_registry()
  adapters = r.get("adapters", {})
  agent = adapters.get("agent") or {}
  targets = set((agent.get("targets") or {}).keys())
  assert targets == AGENT_SHARED_VERBS, (
      f"agent registry targets {sorted(targets)} do not match shared "
      f"protocol surface {sorted(AGENT_SHARED_VERBS)}"
  )


def test_agent_docs_verbs_locked_to_shared_surface():
  text = _load_docs_adapter_registry()

  # Look for the agent section header and the verbs line.
  # We expect a line like: - **verbs**: `send_task`, `read_result`
  agent_section_match = re.search(
      r"## 8\. Agent coordination adapter – `agent`(.+?)(?:## |\Z)",
      text,
      flags=re.DOTALL,
  )
  assert agent_section_match, "agent section missing from ADAPTER_REGISTRY.md"
  section = agent_section_match.group(1)

  verbs_line_match = re.search(r"- \*\*verbs\*\*: `([^`]+)`", section)
  assert verbs_line_match, "agent verbs line missing from ADAPTER_REGISTRY.md"

  verbs_raw = verbs_line_match.group(1)
  # Split on comma and strip spaces, e.g. "send_task`, `read_result"
  verbs = {v.strip() for v in verbs_raw.split(",")}
  assert verbs == AGENT_SHARED_VERBS, (
      f"agent docs verbs {sorted(verbs)} do not match shared "
      f"protocol surface {sorted(AGENT_SHARED_VERBS)}"
  )

