"""Strict validation for examples/wishlist/*.ainl (no network/runtime)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wishlist_graphs():
    root = _repo_root() / "examples" / "wishlist"
    return sorted(root.glob("0*.ainl"))


def test_wishlist_examples_validate_strict():
    root = _repo_root()
    for path in _wishlist_graphs():
        proc = subprocess.run(
            [sys.executable, "-m", "cli.main", "validate", str(path), "--strict"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{path.name} stderr: {proc.stderr}\nstdout: {proc.stdout}"
        data = json.loads(proc.stdout)
        assert data.get("ok") is True, f"{path.name}: {data.get('errors')}"


def test_armaraos_wishlist_host_smoke_strict_if_present():
    """When the ArmaraOS repo is checked out as a sibling of AI_Native_Lang, validate the host smoke graph."""
    smoke = (_repo_root().parent / "armaraos" / "programs" / "wishlist-host-kit" / "wishlist_host_smoke.ainl").resolve()
    if not smoke.is_file():
        return
    root = _repo_root()
    proc = subprocess.run(
        [sys.executable, "-m", "cli.main", "validate", str(smoke), "--strict"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"wishlist_host_smoke stderr: {proc.stderr}\nstdout: {proc.stdout}"
    data = json.loads(proc.stdout)
    assert data.get("ok") is True, data.get("errors")
