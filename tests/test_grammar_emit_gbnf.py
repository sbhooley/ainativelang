"""
Tests for tooling.grammar_emit_gbnf — GBNF grammar emission for constrained decoding.

Round-trip test: every strict-valid example in tooling/artifact_profiles.json must
be structurally compatible with the emitted grammar (basic structural checks since
we don't have a GBNF parser in Python).
"""
import json
import os
import re
import pytest

from tooling.grammar_emit_gbnf import emit_gbnf

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_PATH = os.path.join(REPO_ROOT, "tooling", "artifact_profiles.json")


def _load_strict_valid_paths():
    with open(PROFILES_PATH) as f:
        profiles = json.load(f)
    return profiles.get("examples", {}).get("strict-valid", [])


def test_emit_gbnf_produces_valid_grammar():
    gbnf = emit_gbnf()
    assert len(gbnf) > 100, "GBNF grammar too short"
    assert "root ::=" in gbnf, "Missing root production"
    assert "program ::=" in gbnf, "Missing program production"
    assert "label-header" in gbnf
    assert "compact-header" in gbnf or "compact-block" in gbnf
    assert "adapter-call" in gbnf
    assert "r-line" in gbnf


def test_emit_gbnf_includes_adapter_names():
    gbnf = emit_gbnf()
    assert "core" in gbnf
    assert "http" in gbnf


def test_emit_gbnf_no_compact():
    gbnf_no_compact = emit_gbnf(include_compact=False)
    assert "compact-header ::=" not in gbnf_no_compact, "compact rules should be excluded"
    assert "compact-block ::=" not in gbnf_no_compact, "compact rules should be excluded"


def test_emit_gbnf_deterministic():
    g1 = emit_gbnf()
    g2 = emit_gbnf()
    assert g1 == g2, "Grammar emission should be deterministic"


def _gbnf_structural_check(source: str) -> bool:
    """Quick structural validation: does the source look like it could match the grammar?

    This is a coarse check — it verifies that every non-blank, non-comment line
    matches at least one of the AINL structural patterns. It does NOT replace
    actual compiler validation.
    """
    lines = source.strip().splitlines()
    if not lines:
        return False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^L\d+", stripped):
            continue
        if re.match(r"^S\s+", stripped):
            continue
        if re.match(r"^[A-Z]\w*\s+", stripped):
            continue
        if re.match(r"^include\s+", stripped):
            continue
        if re.match(r"^\w+\s*.*:\s*$", stripped):
            continue
        if re.match(r"^\w+\s*=\s+", stripped):
            continue
        if re.match(r"^(in|out|err|call|if|config|state)[\s:]", stripped):
            continue
        if re.match(r"^\w+\.\w+[\s(]", stripped):
            continue
        if re.match(r"^@", stripped):
            continue
        return False
    return True


@pytest.mark.parametrize(
    "example_path",
    _load_strict_valid_paths(),
    ids=lambda p: os.path.basename(p),
)
def test_strict_valid_example_compatible_with_grammar(example_path):
    full_path = os.path.join(REPO_ROOT, example_path)
    if not os.path.exists(full_path):
        pytest.skip(f"Example file not found: {example_path}")
    with open(full_path) as f:
        source = f.read()
    assert _gbnf_structural_check(source), (
        f"Example {example_path} does not match basic grammar structure"
    )
