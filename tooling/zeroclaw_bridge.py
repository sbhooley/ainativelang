"""ZeroClaw-only extras for ainl install-mcp / install-zeroclaw (repo bridge + shim)."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Callable, Optional


def detect_ainl_repo_root(from_dir: Optional[Path] = None) -> Optional[Path]:
    """Find AI_Native_Lang checkout (pyproject.toml + zeroclaw bridge)."""
    start = (from_dir or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").is_file() and (p / "zeroclaw" / "bridge" / "zeroclaw_bridge_main.py").is_file():
            return p
    return None


def _toml_escape_path(p: Path) -> str:
    return str(p.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def ensure_config_toml_ainl_bridge(
    *,
    home: Path,
    repo_root: Path,
    dry_run: bool,
    verbose: bool,
    log: Callable[[bool, str], None],
) -> None:
    """Append ``[ainl_bridge]`` with ``repo_root`` to ~/.zeroclaw/config.toml if missing."""
    zc = home / Path(".zeroclaw")
    cfg = zc / "config.toml"
    block = (
        "\n# AINL native bridge (ainl install-mcp --host zeroclaw)\n"
        "[ainl_bridge]\n"
        f'repo_root = "{_toml_escape_path(repo_root)}"\n'
    )
    if cfg.is_file():
        try:
            existing = cfg.read_text(encoding="utf-8")
        except OSError:
            existing = ""
        if "[ainl_bridge]" in existing:
            log(verbose, f"config.toml already has [ainl_bridge]: {cfg}")
            return
        if dry_run:
            print(f"[dry-run] would append [ainl_bridge] to {cfg}")
            log(verbose, block.strip())
            return
        zc.mkdir(parents=True, exist_ok=True)
        cfg.write_text(existing.rstrip() + block, encoding="utf-8")
        print(f"Updated ZeroClaw config: {cfg} ([ainl_bridge].repo_root)")
        return
    if dry_run:
        print(f"[dry-run] would create {cfg} with [ainl_bridge]")
        return
    zc.mkdir(parents=True, exist_ok=True)
    cfg.write_text(block.lstrip(), encoding="utf-8")
    print(f"Wrote ZeroClaw config: {cfg}")


def _zeroclaw_ainl_run_shim_body(repo_root: Path) -> str:
    q = _toml_escape_path(repo_root)
    return f"""#!/usr/bin/env bash
set -euo pipefail
export AINL_REPO_ROOT="{q}"
cd "$AINL_REPO_ROOT"
exec python3 "$AINL_REPO_ROOT/zeroclaw/bridge/run_wrapper_ainl.py" "$@"
"""


def ensure_zeroclaw_ainl_run_shim(
    *,
    home: Path,
    repo_root: Path,
    dry_run: bool,
    verbose: bool,
    log: Callable[[bool, str], None],
) -> Path:
    """Install ~/.zeroclaw/bin/zeroclaw-ainl-run → run_wrapper_ainl.py in repo_root."""
    zc_bin = home / Path(".zeroclaw") / "bin"
    target = zc_bin / "zeroclaw-ainl-run"
    body = _zeroclaw_ainl_run_shim_body(repo_root)
    if dry_run:
        print(f"[dry-run] would create {target} (mode +x)")
        log(verbose, body)
        return target
    zc_bin.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    mode = target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    target.chmod(mode)
    print(f"Installed shim: {target}")
    return target
