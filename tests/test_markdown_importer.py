import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from tooling.markdown_importer import (
    generate_stub_ainl,
    github_blob_url_to_raw,
    import_markdown_to_ainl,
    load_markdown_source,
    markdown_to_ainl_from_body,
    schedule_to_cron,
)


def test_github_blob_to_raw():
    u = "https://github.com/nikilster/clawflows/blob/main/workflows/foo/WORKFLOW.md"
    assert "raw.githubusercontent.com" in github_blob_url_to_raw(u)
    assert "/main/workflows/foo/WORKFLOW.md" in github_blob_url_to_raw(u)


def test_load_markdown_local(tmp_path):
    p = tmp_path / "w.md"
    p.write_text("# Hello\n\nStep one.\n", encoding="utf-8")
    label, body = load_markdown_source(str(p))
    assert str(p.resolve()) == label
    assert "Step one" in body


def test_stub_compiles_workflow_and_agent():
    c = AICodeCompiler(strict_mode=False)
    for t in ("workflow", "agent"):
        src = generate_stub_ainl(
            provenance="/tmp/x.md",
            md_type=t,
            markdown_preview="# X",
            openclaw_bridge=True,
        )
        ir = c.compile(src)
        assert not ir.get("errors"), ir.get("errors")


def test_import_markdown_to_ainl_local(tmp_path):
    p = tmp_path / "agent.md"
    p.write_text("---\nname: Test\n---\nDo the thing.\n", encoding="utf-8")
    ainl, meta = import_markdown_to_ainl(str(p), md_type="agent", personality="witty")
    assert meta["markdown_chars"] > 10
    assert "witty" in ainl
    ir = AICodeCompiler(strict_mode=False).compile(ainl)
    assert not ir.get("errors")


def test_workflow_parsed_cron_and_steps():
    md = """---
name: demo-wf
schedule: "9am"
---

# Demo

## 1. First

x

## 2. Second

y
"""
    ainl, meta = markdown_to_ainl_from_body(md, provenance="inline", md_type="workflow", openclaw_bridge=False)
    assert meta.get("parsed") is True
    assert meta.get("cron") == "0 9 * * *"
    assert "L_step_1" in ainl and "L_step_2" in ainl
    assert 'S core cron "0 9 * * *"' in ainl
    ir = AICodeCompiler(strict_mode=False).compile(ainl)
    assert not ir.get("errors")


def test_workflow_fallback_no_steps():
    md = "# Title only\n\nNo numbered headings or lists.\n"
    ainl, meta = markdown_to_ainl_from_body(md, provenance="inline", md_type="workflow")
    assert meta.get("fallback_stub") is True
    assert "stub" in ainl.lower()
    ir = AICodeCompiler(strict_mode=False).compile(ainl)
    assert not ir.get("errors")


def test_generate_soul_sidecars_in_meta():
    md = "---\nname: SoulTest\n---\n# X\n## Mission\nGo.\n"
    _ainl, meta = markdown_to_ainl_from_body(
        md,
        provenance="inline",
        md_type="agent",
        generate_soul=True,
    )
    sc = meta.get("sidecars")
    assert sc and "SOUL.md" in sc and "IDENTITY.md" in sc
    assert "SoulTest" in sc["SOUL.md"]


def test_schedule_to_cron_explicit():
    cron, _ = schedule_to_cron({"cron": "*/10 * * * *"}, "")
    assert cron == "*/10 * * * *"
