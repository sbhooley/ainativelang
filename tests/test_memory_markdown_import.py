from pathlib import Path

from runtime.adapters.memory import MemoryAdapter
from tooling.memory_markdown_import import (
    SUPPORTED_KINDS,
    collect_markdown_envelopes,
    import_markdown_to_memory,
)


def _write_md(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_collect_envelopes_project_fact(tmp_path):
    md = """---
ainl_namespace: long_term
ainl_record_kind: long_term.project_fact
ainl_record_id: proj-123
ainl_source_system: obsidian
ainl_authored_by: human
ainl_authoritative: true
ainl_curated: true
---
This is a curated project fact.
"""
    p = _write_md(tmp_path, "fact.md", md)
    envs = collect_markdown_envelopes([p])
    assert len(envs) == 1
    env = envs[0]
    assert env["namespace"] == "long_term"
    assert env["record_kind"] == "long_term.project_fact"
    assert env["record_id"] == "proj-123"
    assert env["payload"]["text"].strip() == "This is a curated project fact."
    assert env["provenance"]["source_system"] == "markdown" or env["provenance"]["source_system"] == "obsidian"
    assert env["flags"]["curated"] is True


def test_collect_envelopes_user_preference_with_key_value(tmp_path):
    md = """---
ainl_namespace: long_term
ainl_record_kind: long_term.user_preference
ainl_record_id: pref-theme
preference_key: theme
preference_value: dark
---
User prefers dark theme.
"""
    p = _write_md(tmp_path, "pref.md", md)
    envs = collect_markdown_envelopes([p])
    assert len(envs) == 1
    env = envs[0]
    assert env["record_kind"] == "long_term.user_preference"
    payload = env["payload"]
    assert payload["key"] == "theme"
    assert payload["value"] == "dark"
    assert "User prefers dark theme." in payload["text"]


def test_collect_envelopes_missing_frontmatter_skipped(tmp_path):
    md = "# No frontmatter\nJust a note."
    p = _write_md(tmp_path, "plain.md", md)
    envs = collect_markdown_envelopes([p])
    assert envs == []


def test_collect_envelopes_unsupported_kind_skipped(tmp_path):
    ns, rk = SUPPORTED_KINDS[0]
    wrong_kind = "daily_log.note"
    md = f"""---
ainl_namespace: {ns}
ainl_record_kind: {wrong_kind}
ainl_record_id: something
---
Body.
"""
    p = _write_md(tmp_path, "wrong.md", md)
    envs = collect_markdown_envelopes([p])
    assert envs == []


def test_import_markdown_directory_into_memory(tmp_path):
    db_path = tmp_path / "memory.sqlite3"

    md1 = """---
ainl_namespace: long_term
ainl_record_kind: long_term.project_fact
ainl_record_id: fact-1
---
Fact one.
"""
    md2 = """---
ainl_namespace: long_term
ainl_record_kind: long_term.user_preference
ainl_record_id: pref-editor
preference_key: editor
preference_value: vim
---
Prefers vim.
"""
    d = tmp_path / "notes"
    d.mkdir()
    _write_md(d, "fact1.md", md1)
    _write_md(d, "pref1.md", md2)

    result = import_markdown_to_memory(str(db_path), [d])
    assert result.ok
    assert result.inserted == 2

    adp = MemoryAdapter(db_path=str(db_path))

    res_fact = adp.call(
        "get",
        ["long_term", "long_term.project_fact", "fact-1"],
        {},
    )
    assert res_fact["found"] is True
    fact_payload = res_fact["record"]["payload"]
    assert "Fact one." in fact_payload["text"]

    res_pref = adp.call(
        "get",
        ["long_term", "long_term.user_preference", "pref-editor"],
        {},
    )
    assert res_pref["found"] is True
    pref_payload = res_pref["record"]["payload"]
    assert pref_payload["key"] == "editor"
    assert pref_payload["value"] == "vim"


def test_import_markdown_validation_failure(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    # Invalid namespace should be rejected by validator
    md = """---
ainl_namespace: invalid_ns
ainl_record_kind: long_term.project_fact
ainl_record_id: fact-bad
---
Bad fact.
"""
    p = _write_md(tmp_path, "bad.md", md)
    result = import_markdown_to_memory(str(db_path), [p])
    assert not result.ok
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors

