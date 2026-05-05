"""Tests for the one-step ``ainl setup`` agent installer.

Covers detection, idempotent merge semantics, atomic write + backup, dry-run,
and the generic-MCP fallback. All filesystem effects are confined to a
``tmp_path`` HOME — no real config files are touched.
"""

from __future__ import annotations

import io
import json
import os
import platform
from pathlib import Path

import pytest

from tooling import agent_setup


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _seed_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_detect_no_hosts_returns_empty(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    found = agent_setup.detect_hosts(home=home, cwd=cwd, system="Darwin", env={})
    assert found == []


def test_detect_claude_code_project_via_mcp_json(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / ".mcp.json").write_text("{}", encoding="utf-8")
    found = agent_setup.detect_hosts(home=home, cwd=cwd, system="Darwin", env={})
    kinds = [h.kind for h in found]
    assert "claude-code-project" in kinds


def test_detect_cursor_via_dir(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".cursor").mkdir()
    found = agent_setup.detect_hosts(home=home, cwd=tmp_path, system="Darwin", env={})
    assert any(h.kind == "cursor" for h in found)


def test_detect_codex_cli_via_dot_codex(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".codex").mkdir()
    found = agent_setup.detect_hosts(home=home, cwd=tmp_path, system="Linux", env={})
    h = next(h for h in found if h.kind == "codex-cli")
    assert h.config_path == home / ".codex" / "config.toml"


def test_detect_claude_desktop_macos(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    cd = home / "Library" / "Application Support" / "Claude"
    cd.mkdir(parents=True)
    (cd / "claude_desktop_config.json").write_text("{}", encoding="utf-8")
    found = agent_setup.detect_hosts(home=home, cwd=tmp_path, system="Darwin", env={})
    assert any(h.kind == "claude-desktop" for h in found)


def test_detect_cline_macos(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / "Library" / "Application Support" / "Cline").mkdir(parents=True)
    found = agent_setup.detect_hosts(home=home, cwd=tmp_path, system="Darwin", env={})
    assert any(h.kind == "cline" for h in found)


def test_detect_codex_desktop_windows(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    appdata = tmp_path / "AppData"
    (appdata / "Codex").mkdir(parents=True)
    (appdata / "Codex" / "config.json").write_text("{}", encoding="utf-8")
    found = agent_setup.detect_hosts(
        home=home, cwd=tmp_path, system="Windows", env={"APPDATA": str(appdata)}
    )
    assert any(h.kind == "codex-desktop" for h in found)


def test_detect_delegated_hosts(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".openclaw").mkdir()
    (home / ".openclaw" / "openclaw.json").write_text("{}", encoding="utf-8")
    (home / ".hermes").mkdir()
    (home / ".armaraos").mkdir()
    (home / ".armaraos" / "config.toml").write_text("", encoding="utf-8")
    found = agent_setup.detect_hosts(home=home, cwd=tmp_path, system="Linux", env={})
    kinds = {h.kind for h in found}
    assert {"openclaw", "hermes", "armaraos"}.issubset(kinds)
    for h in found:
        if h.kind in {"openclaw", "hermes", "armaraos"}:
            assert h.delegate_host == h.kind


# ---------------------------------------------------------------------------
# JSON mcpServers writer — merge, idempotency, backup
# ---------------------------------------------------------------------------


def test_write_json_mcpservers_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    res = agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={"FOO": "bar"},
        dry_run=False,
    )
    assert res.action == "written"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ainl"]["command"] == "/abs/ainl-mcp"
    assert data["mcpServers"]["ainl"]["env"]["FOO"] == "bar"


def test_write_json_mcpservers_preserves_other_servers(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "brainctl": {"command": "/x/brainctl-mcp", "args": []},
                },
                "preferences": {"keep": "this"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={},
        dry_run=False,
    )
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcpServers"]["brainctl"]["command"] == "/x/brainctl-mcp"
    assert data["mcpServers"]["ainl"]["command"] == "/abs/ainl-mcp"
    assert data["preferences"]["keep"] == "this"


def test_write_json_mcpservers_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    for _ in range(3):
        agent_setup.write_json_mcpservers(
            target,
            server_name="ainl",
            command="/abs/ainl-mcp",
            env={},
            dry_run=False,
        )
    data = json.loads(target.read_text(encoding="utf-8"))
    # Exactly one ainl entry, no duplicates.
    assert list(data["mcpServers"].keys()) == ["ainl"]


def test_write_json_mcpservers_replaces_existing_ainl(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {"mcpServers": {"ainl": {"command": "/old/ainl-mcp", "args": []}}}
        ),
        encoding="utf-8",
    )
    agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/new/ainl-mcp",
        env={},
        dry_run=False,
    )
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ainl"]["command"] == "/new/ainl-mcp"


def test_write_json_mcpservers_creates_backup(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text('{"mcpServers": {}}', encoding="utf-8")
    res = agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={},
        dry_run=False,
    )
    assert res.backup_path is not None
    assert res.backup_path.exists()
    assert res.backup_path.read_text(encoding="utf-8") == '{"mcpServers": {}}'


def test_write_json_mcpservers_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    res = agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={},
        dry_run=True,
    )
    assert res.action == "dry-run"
    assert not target.exists()


def test_write_json_mcpservers_recovers_from_corrupt_json(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text("{not json", encoding="utf-8")
    agent_setup.write_json_mcpservers(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={},
        dry_run=False,
    )
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ainl"]["command"] == "/abs/ainl-mcp"


# ---------------------------------------------------------------------------
# Codex CLI TOML writer
# ---------------------------------------------------------------------------


def test_write_codex_cli_toml_creates_block(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        'model = "gpt-5.5"\n[features]\njs_repl = true\n', encoding="utf-8"
    )
    agent_setup.write_codex_cli_toml(
        target,
        server_name="ainl",
        command="/abs/ainl-mcp",
        env={"AINL_MCP_AGENT_ID": "ainl-via-codex-cli"},
        dry_run=False,
        cwd_value="/Users/me",
    )
    text = target.read_text(encoding="utf-8")
    assert "[mcp_servers.ainl]" in text
    assert 'command = "/abs/ainl-mcp"' in text
    assert "enabled = true" in text
    assert 'model = "gpt-5.5"' in text  # preserved
    # Validity check (Python 3.11+ has tomllib; older skips)
    try:
        import tomllib

        tomllib.loads(text)
    except ImportError:
        pass


def test_write_codex_cli_toml_replaces_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        '[mcp_servers.ainl]\ncommand = "/old/path"\nenabled = true\n\n[features]\njs_repl = true\n',
        encoding="utf-8",
    )
    agent_setup.write_codex_cli_toml(
        target,
        server_name="ainl",
        command="/new/path",
        env={},
        dry_run=False,
    )
    text = target.read_text(encoding="utf-8")
    assert text.count("[mcp_servers.ainl]") == 1  # no duplicates
    assert '"/old/path"' not in text
    assert '"/new/path"' in text
    assert "[features]" in text  # unrelated section preserved


def test_write_codex_cli_toml_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    for _ in range(3):
        agent_setup.write_codex_cli_toml(
            target,
            server_name="ainl",
            command="/abs/ainl-mcp",
            env={},
            dry_run=False,
        )
    text = target.read_text(encoding="utf-8")
    assert text.count("[mcp_servers.ainl]") == 1


# ---------------------------------------------------------------------------
# resolve_ainl_mcp_command
# ---------------------------------------------------------------------------


def test_resolve_command_prefers_explicit_absolute(tmp_path: Path) -> None:
    explicit = tmp_path / "ainl-mcp"
    out = agent_setup.resolve_ainl_mcp_command(prefer=str(explicit))
    assert out == str(explicit)


def test_resolve_command_falls_back_to_bare_when_missing() -> None:
    # If shutil.which returns None and sys.prefix candidates don't exist, we
    # fall back to the bare name. This is a contract for the fallback path.
    out = agent_setup.resolve_ainl_mcp_command(prefer="this/path/does/not/exist")
    assert out  # something gets returned, never raises


# ---------------------------------------------------------------------------
# run_setup orchestration
# ---------------------------------------------------------------------------


def test_run_setup_print_config_only(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = agent_setup.run_setup(
        home=_seed_home(tmp_path),
        cwd=tmp_path,
        print_config_only=True,
        out=out,
        err=err,
    )
    assert rc == 0
    data = json.loads(out.getvalue())
    assert "ainl" in data["mcpServers"]


def test_run_setup_no_hosts_prints_generic_block(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = agent_setup.run_setup(
        home=_seed_home(tmp_path),
        cwd=tmp_path,
        no_verify=True,
        out=out,
        err=err,
        env={},
        system="Linux",
    )
    assert rc == 0
    assert "mcpServers" in out.getvalue()
    assert "no host detected" in err.getvalue()


def test_run_setup_writes_detected_hosts(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".cursor").mkdir()
    out = io.StringIO()
    err = io.StringIO()
    rc = agent_setup.run_setup(
        home=home,
        cwd=tmp_path,
        no_verify=True,
        out=out,
        err=err,
        env={},
        system="Linux",
    )
    assert rc == 0
    cursor_cfg = home / ".cursor" / "mcp.json"
    assert cursor_cfg.exists()
    data = json.loads(cursor_cfg.read_text(encoding="utf-8"))
    assert "ainl" in data["mcpServers"]


def test_run_setup_dry_run_writes_nothing(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".cursor").mkdir()
    out = io.StringIO()
    err = io.StringIO()
    rc = agent_setup.run_setup(
        home=home,
        cwd=tmp_path,
        dry_run=True,
        no_verify=True,
        out=out,
        err=err,
        env={},
        system="Linux",
    )
    assert rc == 0
    assert not (home / ".cursor" / "mcp.json").exists()


def test_run_setup_target_host_unknown_returns_2(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = agent_setup.run_setup(
        home=_seed_home(tmp_path),
        cwd=tmp_path,
        target_host="not-a-real-host",
        no_verify=True,
        out=out,
        err=err,
    )
    assert rc == 2
    assert "unknown host" in err.getvalue()


def test_run_setup_delegate_invoked_for_legacy_hosts(tmp_path: Path) -> None:
    home = _seed_home(tmp_path)
    (home / ".openclaw").mkdir()
    (home / ".openclaw" / "openclaw.json").write_text("{}", encoding="utf-8")
    out = io.StringIO()
    err = io.StringIO()
    calls: list[tuple[str, bool, bool]] = []

    def fake_delegate(host: str, dry_run: bool, verbose: bool) -> int:
        calls.append((host, dry_run, verbose))
        return 0

    rc = agent_setup.run_setup(
        home=home,
        cwd=tmp_path,
        no_verify=True,
        out=out,
        err=err,
        delegate=fake_delegate,
        env={},
        system="Linux",
    )
    assert rc == 0
    assert ("openclaw", False, False) in calls


# ---------------------------------------------------------------------------
# Generic MCP block shape
# ---------------------------------------------------------------------------


def test_generic_block_is_well_formed_json() -> None:
    text = agent_setup.render_generic_mcp_block(
        command="/abs/ainl-mcp", env={"AINL_MCP_AGENT_ID": "x"}
    )
    data = json.loads(text)
    assert data["mcpServers"]["ainl"]["command"] == "/abs/ainl-mcp"
    assert data["mcpServers"]["ainl"]["env"]["AINL_MCP_AGENT_ID"] == "x"
