"""``ainl emit --target armaraos`` HAND pack layout and artifact contracts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_STEM = "hp_fixture"

_SOURCE_CORE = f"""{_STEM}:
 in: msg
 result = core.CONCAT msg "!"
 out result
"""

_SOURCE_WITH_HTTP = """S app api /api
L1:
R http.GET "https://example.com" ->resp
J resp
"""

_SOURCE_J_ONLY = """S app core noop
L1:
J 42
"""


def _write_source(tmp_path: Path, text: str) -> Path:
    p = tmp_path / f"{_STEM}.ainl"
    p.write_text(text, encoding="utf-8")
    return p


def _run_emit(src: Path, out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli.main", "emit", str(src), "--target", "armaraos", "-o", str(out_dir)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def test_emit_armaraos_required_artifacts_only(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand_out"
    res = _run_emit(src, out_dir)
    assert res.returncode == 0, res.stderr
    names = {p.name for p in out_dir.iterdir()}
    assert names == {"HAND.toml", f"{_STEM}.ainl.json", "security.json", "README.md"}


def test_hand_toml_required_keys_and_entrypoint(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand2"
    assert _run_emit(src, out_dir).returncode == 0
    hand = (out_dir / "HAND.toml").read_text(encoding="utf-8")
    assert "[hand]" in hand
    for key in ("name =", "version =", "entrypoint =", "ainl_ir_version ="):
        assert key in hand
    assert f'entrypoint = "{_STEM}.ainl.json"' in hand
    m = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', hand)
    assert m, hand


def test_security_json_capabilities_match_source_adapters(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_WITH_HTTP)
    out_dir = tmp_path / "hand3"
    assert _run_emit(src, out_dir).returncode == 0
    sec = json.loads((out_dir / "security.json").read_text(encoding="utf-8"))
    decl = sec.get("capability_declarations") or {}
    adapters = set(decl.get("adapters") or [])
    assert "http" in adapters


def test_security_json_empty_capabilities_when_no_adapter_ops(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_J_ONLY)
    out_dir = tmp_path / "hand4"
    assert _run_emit(src, out_dir).returncode == 0
    sec = json.loads((out_dir / "security.json").read_text(encoding="utf-8"))
    decl = sec.get("capability_declarations") or {}
    assert decl.get("adapters") in (None, [])


def test_readme_nonempty_contains_program_name(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand5"
    assert _run_emit(src, out_dir).returncode == 0
    body = (out_dir / "README.md").read_text(encoding="utf-8")
    assert len(body.strip()) > 20
    assert _STEM in body


def test_ainl_json_is_valid_ir(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand6"
    assert _run_emit(src, out_dir).returncode == 0
    ir = json.loads((out_dir / f"{_STEM}.ainl.json").read_text(encoding="utf-8"))
    assert "labels" in ir or "nodes" in ir


def test_emit_hand_toml_contains_hand_schema_version(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand_schema_toml"
    assert _run_emit(src, out_dir).returncode == 0
    hand = (out_dir / "HAND.toml").read_text(encoding="utf-8")
    assert 'schema_version = "1"' in hand


def test_emit_ainl_json_contains_ir_schema_version(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand_schema_ir"
    assert _run_emit(src, out_dir).returncode == 0
    ir = json.loads((out_dir / f"{_STEM}.ainl.json").read_text(encoding="utf-8"))
    assert ir.get("schema_version") == "1"


def test_emit_security_json_contains_schema_version(tmp_path: Path):
    src = _write_source(tmp_path, _SOURCE_CORE)
    out_dir = tmp_path / "hand_schema_sec"
    assert _run_emit(src, out_dir).returncode == 0
    sec = json.loads((out_dir / "security.json").read_text(encoding="utf-8"))
    assert sec.get("schema_version") == "1"


def test_emit_ir_schema_version_stable_across_two_emits(tmp_path: Path):
    """Emitter must not mutate the caller's IR dict; schema_version on disk stays stable."""
    from armaraos.emitter.armaraos import emit_armaraos

    ir: dict = {"labels": {"L1": []}, "metadata": {}, "ir_version": "test"}
    out_a = tmp_path / "emit_a"
    out_b = tmp_path / "emit_b"
    emit_armaraos(ir, _STEM, out_a)
    assert "schema_version" not in ir, "emit_armaraos must not mutate caller IR dict in place"
    emit_armaraos(ir, _STEM, out_b)
    ja = json.loads((out_a / f"{_STEM}.ainl.json").read_text(encoding="utf-8"))
    jb = json.loads((out_b / f"{_STEM}.ainl.json").read_text(encoding="utf-8"))
    assert ja.get("schema_version") == jb.get("schema_version") == "1"
