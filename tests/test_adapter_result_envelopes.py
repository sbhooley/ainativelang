import json
import os
import sys
from typing import Dict, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_manifest() -> Dict:
  root = os.path.dirname(os.path.dirname(__file__))
  p = os.path.join(root, "tooling", "adapter_manifest.json")
  with open(p, "r", encoding="utf-8") as f:
      return json.load(f)


def _load_adapter_docs() -> str:
  root = os.path.dirname(os.path.dirname(__file__))
  p = os.path.join(root, "docs", "reference", "ADAPTER_REGISTRY.md")
  with open(p, "r", encoding="utf-8") as f:
      return f.read()


EXPECTED_ENVELOPES: Dict[str, Set[str]] = {
  "http": {"ok", "status_code", "error", "body", "headers", "url", "payment"},
  "queue": {"ok", "message_id", "queue_name", "error"},
  "svc": {"ok", "status", "latency_ms", "error"},
}


def test_manifest_declares_expected_result_envelope_fields():
  manifest = _load_manifest()["adapters"]

  for name, fields in EXPECTED_ENVELOPES.items():
      assert name in manifest, f"adapter {name!r} missing from manifest"
      env = manifest[name].get("result_envelope") or {}
      manifest_fields = set((env.get("fields") or {}).keys())
      assert manifest_fields == fields, f"{name}.result_envelope.fields mismatch: {manifest_fields} != {fields}"


def test_adapter_registry_docs_mention_result_envelope_fields():
  text = _load_adapter_docs()

  for name, fields in EXPECTED_ENVELOPES.items():
      # Weak but useful consistency check: all field names appear in the docs.
      for field in fields:
          assert field in text, f"field {name}.{field} missing from ADAPTER_REGISTRY.md"
