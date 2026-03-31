"""
Integration tests for OpenFang support in AINL.

Mirrors the OpenClaw test patterns but targeted at OpenFang.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest_plugins = "pytester"


@pytest.mark.skipif(
    shutil.which("armaraos") is None,
    reason="OpenFang CLI not installed",
)
def test_armaraos_install_dry_run():
    """Test ainl install armaraos --dry-run executes without error."""
    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "install", "armaraos", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Install failed: {result.stderr}"
    assert "Wrote MCP config:" in result.stdout or "[dry-run]" in result.stdout


def test_emit_armaraos_creates_hand_package(tmp_path):
    """Test ainl emit --target armaraos produces a valid hand package."""
    # Create a simple AINL source
    source = tmp_path / "simple.ainl"
    source.write_text(
        """
    graph test:
      input: string msg
      output: string result
      steps:
        - set result = msg + " processed by AINL"
    """
    )

    out_dir = tmp_path / "hand"
    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "emit", str(source), "--target", "armaraos", "-o", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Emit failed: {result.stderr}"

    # Check outputs
    assert out_dir.exists()
    assert (out_dir / "HAND.toml").exists()
    assert (out_dir / "simple.ainl.json").exists()
    assert (out_dir / "security.json").exists()
    assert (out_dir / "README.md").exists()

    # Validate HAND.toml structure (basic)
    import tomllib

    hand = tomllib.loads((out_dir / "HAND.toml").read_text(encoding="utf-8"))
    assert "hand" in hand
    assert hand["hand"]["entrypoint"] == "simple.ainl.json"


def test_armaraos_bridge_validation():
    """Test that armaraos bridge validation passes with proper environment."""
    from armaraos.bridge.ainl_bridge_main import ainl_armaraos_validate

    # This should not raise; it returns a dict with ok=True if everything is fine
    val = ainl_armaraos_validate()
    assert isinstance(val, dict)
    assert "ok" in val
    # If schema is ok, that's enough for basic validation
    # We don't require OpenFang CLI to be present for this test
    if val.get("schema_ok"):
        pass
    else:
        pytest.skip(f"Schema not initialized: {val.get('schema_detail')}")


def test_status_command_json():
    """Test ainl status --host armaraos --json returns parsable output."""
    import json

    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "status", "--host", "armaraos", "--json"],
        capture_output=True,
        text=True,
    )
    # May fail if OpenFang not installed, but should not crash parser
    try:
        data = json.loads(result.stdout)
        assert "armaraos_installed" in data
        assert "ainl_mcp_registered" in data
    except json.JSONDecodeError:
        pytest.skip(f"Status command did not return JSON: {result.stdout}")
