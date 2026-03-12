from pathlib import Path

from runtime.adapters.memory import MemoryAdapter
from tooling.memory_migrate import (
    _parse_memory_md_sections,
    _parse_legacy_daily_log_file,
    migrate_legacy_memory,
)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_memory_md_sections_splits_on_headings():
    text = """# Title

## Section One
Line A
- Bullet B

## Section Two
Line C
"""
    sections = _parse_memory_md_sections(text)
    assert len(sections) == 2
    heads = [h for h, _ in sections]
    assert heads == ["Section One", "Section Two"]


def test_migrate_memory_md_creates_project_facts(tmp_path):
    memory_md = """# MEMORY

## AINL Knowledge Base
Line about AINL.

## Infrastructure
Infra details.
"""
    mem_path = _write(tmp_path, "MEMORY.md", memory_md)
    db_path = tmp_path / "memory.sqlite3"

    result = migrate_legacy_memory(str(db_path), mem_path, None)
    assert result.ok
    assert result.inserted == 2

    adp = MemoryAdapter(db_path=str(db_path))

    res1 = adp.call(
        "get",
        ["long_term", "long_term.project_fact", "memory_md.ainl_knowledge_base"],
        {},
    )
    assert res1["found"] is True
    assert "Line about AINL." in res1["record"]["payload"]["text"]

    res2 = adp.call(
        "get",
        ["long_term", "long_term.project_fact", "memory_md.infrastructure"],
        {},
    )
    assert res2["found"] is True
    assert "Infra details." in res2["record"]["payload"]["text"]


def test_parse_legacy_daily_log_file_creates_entries(tmp_path):
    log = """- [2026-03-09T01:00:00Z] First event
- Second event
Plain line
"""
    p = _write(tmp_path, "2026-03-09.md", log)
    env = _parse_legacy_daily_log_file(p)
    assert env is not None
    assert env["namespace"] == "daily_log"
    assert env["record_kind"] == "daily_log.note"
    assert env["record_id"] == "2026-03-09"
    entries = env["payload"]["entries"]
    assert len(entries) == 3
    assert entries[0]["ts"] == "2026-03-09T01:00:00Z"
    assert entries[0]["text"] == "First event"


def test_migrate_daily_logs_directory(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    _write(
        mem_dir,
        "2026-03-10.md",
        "- [2026-03-10T09:00:00Z] Start day\n- Check monitor\n",
    )

    db_path = tmp_path / "memory.sqlite3"
    result = migrate_legacy_memory(str(db_path), None, mem_dir)
    assert result.ok
    assert result.inserted == 1

    adp = MemoryAdapter(db_path=str(db_path))
    res = adp.call(
        "get",
        ["daily_log", "daily_log.note", "2026-03-10"],
        {},
    )
    assert res["found"] is True
    payload = res["record"]["payload"]
    assert payload["entries"]
    assert any("Start day" in e["text"] for e in payload["entries"])


def test_migrate_no_sources_is_noop(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    result = migrate_legacy_memory(str(db_path), None, None)
    assert result.ok
    assert result.inserted == 0
    assert result.updated == 0

