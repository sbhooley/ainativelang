import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.effect_analysis import ADAPTER_EFFECT


def _load_manifest():
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tooling", "adapter_manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_adapter_manifest_basic_shape():
    m = _load_manifest()
    assert m.get("schema_version") in ("1.0", "1.1")
    adapters = m.get("adapters")
    assert isinstance(adapters, dict) and adapters
    for name, cfg in adapters.items():
        assert isinstance(name, str) and name
        assert isinstance(cfg.get("verbs"), list) and cfg["verbs"]
        assert cfg.get("effect_default") in {"pure", "io", "meta"}
        tier = cfg.get("support_tier")
        assert tier in {"core", "extension_openclaw", "extension_armaraos", "compatibility"}
        strict = cfg.get("strict_contract")
        assert isinstance(strict, bool)
        lane = cfg.get("recommended_lane")
        assert lane in {"canonical", "noncanonical"}


def test_adapter_manifest_covers_effect_analysis_keys():
    m = _load_manifest()
    adapters = m["adapters"]
    for key in ADAPTER_EFFECT.keys():
        namespace, verb = key.split(".", 1)
        assert namespace in adapters, f"missing adapter namespace {namespace!r} for ADAPTER_EFFECT key {key!r}"
        # manifest verbs are case-sensitive declarations; normalize for comparison.
        manifest_verbs = {str(v).upper() for v in adapters[namespace].get("verbs", [])}
        assert verb.upper() in manifest_verbs, f"missing verb {verb!r} under adapter {namespace!r}"
