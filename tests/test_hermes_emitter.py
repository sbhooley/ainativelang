from __future__ import annotations

import json
from pathlib import Path

from compiler_v2 import AICodeCompiler
from hermes.hermes_skill_importer import build_hermes_skill_bundle


def test_hermes_skill_importer_frontmatter_and_artifacts() -> None:
    code = "S app core noop\n\nL1:\n  R core.ADD 2 3 ->sum\n  J sum\n"
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile(code, emit_graph=True, source_path="inline.ainl")
    assert not ir.get("errors")

    bundle = build_hermes_skill_bundle(ir, ainl_source=code, skill_name="demo", source_stem="demo")
    files = dict(bundle.files)
    assert set(files.keys()) == {"SKILL.md", "workflow.ainl", "ir.json"}

    md = files["SKILL.md"]
    assert md.startswith("---\n")
    assert '\nname: "demo"\n' in md
    assert '\nkind: "skill"\n' in md
    assert '\nformat: "markdown"\n' in md
    assert '\ncompat: "agentskills.io"\n' in md
    assert '\ndescription: "' in md
    assert '\nversion: "1.0.0"\n' in md
    assert '\ncategory: "ainl"\n' in md
    assert "\ntags:\n" in md
    assert "\n  - ainl\n" in md
    assert "\n  - deterministic\n" in md
    assert "\n  - mcp\n" in md
    assert "\n---\n" in md

    assert "ainl_run" in md
    assert "Deterministic runtime contract" in md

    parsed_ir = json.loads(files["ir.json"])
    assert isinstance(parsed_ir, dict)
    assert parsed_ir.get("ir_version") == ir.get("ir_version")


def test_compile_emit_hermes_skill_bundle_to_directory(tmp_path: Path) -> None:
    code = (Path(__file__).resolve().parent.parent / "examples" / "hello.ainl").read_text(encoding="utf-8")
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile(code, emit_graph=True, source_path="hello.ainl")
    assert not ir.get("errors")

    bundle = c.emit_hermes_skill_bundle(ir, ainl_source=code, skill_name="hello", source_stem="hello")
    out_dir = tmp_path / "hello_skill"
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in bundle.items():
        p = out_dir / rel
        p.write_text(content, encoding="utf-8")

    assert (out_dir / "SKILL.md").is_file()
    assert (out_dir / "workflow.ainl").is_file()
    assert (out_dir / "ir.json").is_file()

