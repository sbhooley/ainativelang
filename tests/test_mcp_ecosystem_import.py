import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tooling.mcp_ecosystem_import import (
    import_clawflow_mcp,
    list_ecosystem_templates,
)


def test_list_ecosystem_has_presets():
    d = list_ecosystem_templates()
    assert d["clawflows_presets"]
    assert d["agency_agents_presets"]
    slugs = {x["slug"] for x in d["clawflows_presets"]}
    assert "check-calendar" in slugs


def test_import_clawflow_unknown_name():
    out = import_clawflow_mcp("totally-unknown-slug-xyz")
    assert out["ok"] is False
    assert "error" in out
