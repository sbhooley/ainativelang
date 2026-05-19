import json
import os
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


def test_registry_targets_align_with_manifest_verbs_for_overlapping_adapters():
    manifest = _load_manifest()["adapters"]
    registry = _load_registry().get("adapters", {})

    for name, reg_cfg in registry.items():
        if name not in manifest:
            continue
        manifest_verbs = {str(v).upper() for v in manifest[name].get("verbs", [])}
        targets = reg_cfg.get("targets", {}) or {}
        for tgt in targets.keys():
            # registry uses lowercase verbs/targets; compare case-insensitively.
            assert tgt.upper() in manifest_verbs, f"registry verb {name}.{tgt} missing from manifest verbs {sorted(manifest_verbs)}"


# Adapters whose manifest verbs were normalized to UPPERCASE in the
# verb-case-normalization pass to match the canonical strict contract in
# tooling/effect_analysis.py. Adapters that intentionally document both
# cases (svc, tiktok, web, browser, crm, api, auth, bridge, tools, a2a)
# are deliberately excluded — they advertise lowercase aliases the
# runtime accepts.
_NORMALIZED_ADAPTERS = frozenset({
    "cache", "queue", "txn", "http", "sqlite", "postgres", "pggraph", "mysql",
    "redis", "dynamodb", "airtable", "supabase", "fs", "persona", "memory",
})


def test_normalized_adapters_have_uppercase_only_manifest_verbs():
    """Pin the verb-case normalization for adapters covered in the
    cosmetic alignment pass. Prevents a future PR from accidentally
    re-introducing PascalCase or lowercase mixing for these specific
    adapters; adapters with documented dual-case aliases are excluded
    by design."""
    manifest = _load_manifest()["adapters"]
    for name in _NORMALIZED_ADAPTERS:
        verbs = manifest.get(name, {}).get("verbs", [])
        assert verbs, f"{name} has no verbs in manifest"
        non_upper = [v for v in verbs if v != v.upper()]
        assert not non_upper, (
            f"{name}: verbs must be UPPERCASE (canonical strict-contract form); "
            f"non-uppercase entries: {non_upper}"
        )
