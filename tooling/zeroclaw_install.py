"""Bootstrap AINL for ZeroClaw: pip upgrade, MCP stub, ainl-run, optional bridge TOML + zeroclaw-ainl-run shim, PATH hints."""

from __future__ import annotations

import json
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

_ZC_REL = Path(".zeroclaw")
_WRAPPER_NAME = "ainl-run"
_SHIM_ZC_AINL = "zeroclaw-ainl-run"
_PATH_LINE = 'export PATH="$HOME/.zeroclaw/bin:$PATH"'
_MCP_SERVER_KEY = "ainl"


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
) -> None:
    """Append ``[ainl_bridge]`` with ``repo_root`` to ~/.zeroclaw/config.toml if missing."""
    zc = home / _ZC_REL
    cfg = zc / "config.toml"
    block = (
        "\n# AINL native bridge (ainl install-zeroclaw)\n"
        "[ainl_bridge]\n"
        f'repo_root = "{_toml_escape_path(repo_root)}"\n'
    )
    if cfg.is_file():
        try:
            existing = cfg.read_text(encoding="utf-8")
        except OSError:
            existing = ""
        if "[ainl_bridge]" in existing:
            _log(verbose, f"config.toml already has [ainl_bridge]: {cfg}")
            return
        if dry_run:
            print(f"[dry-run] would append [ainl_bridge] to {cfg}")
            _log(verbose, block.strip())
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
) -> Path:
    """Install ~/.zeroclaw/bin/zeroclaw-ainl-run → run_wrapper_ainl.py in repo_root."""
    zc_bin = home / _ZC_REL / "bin"
    target = zc_bin / _SHIM_ZC_AINL
    body = _zeroclaw_ainl_run_shim_body(repo_root)
    if dry_run:
        print(f"[dry-run] would create {target} (mode +x)")
        _log(verbose, body)
        return target
    zc_bin.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    mode = target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    target.chmod(mode)
    print(f"Installed shim: {target}")
    return target


def _log(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def default_run_pip_install(verbose: bool) -> int:
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "ainl-lang[mcp]",
    ]
    _log(verbose, "+ " + " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def _which_or_fallback(name: str, fallback: str) -> str:
    from shutil import which

    p = which(name)
    return p if p else fallback


def _ainl_run_wrapper_lines(ainl_exe: str) -> str:
    # Compile then run the same .ainl; pass remaining args to `ainl run`.
    q = shlex.quote(ainl_exe)
    return f"""#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: {_WRAPPER_NAME} <file.ainl> [extra ainl run args...]" >&2
  exit 1
fi
FILE="$1"
shift
{q} compile "$FILE" && exec {q} run "$FILE" "$@"
"""


def ensure_mcp_registration(
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Merge AINL stdio MCP server into ~/.zeroclaw/mcp.json if not already present."""
    zc = home / _ZC_REL
    mcp_path = zc / "mcp.json"
    ainl_mcp = _which_or_fallback("ainl-mcp", "ainl-mcp")

    desired = {"command": ainl_mcp, "args": []}

    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    if not isinstance(data, dict):
        data = {}

    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        servers = {}

    existing = servers.get(_MCP_SERVER_KEY)
    if isinstance(existing, dict) and existing.get("command") == desired["command"]:
        _log(verbose, f"MCP: {_MCP_SERVER_KEY!r} already registered in {mcp_path}")
        return

    servers[_MCP_SERVER_KEY] = desired
    data["mcpServers"] = servers

    if dry_run:
        print(f"[dry-run] would write/update {mcp_path} with mcpServers.{_MCP_SERVER_KEY}")
        _log(verbose, json.dumps({"mcpServers": {_MCP_SERVER_KEY: desired}}, indent=2))
        return

    zc.mkdir(parents=True, exist_ok=True)
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote MCP config: {mcp_path}")


def ensure_ainl_run_wrapper(
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> Path:
    zc_bin = home / _ZC_REL / "bin"
    target = zc_bin / _WRAPPER_NAME
    ainl_exe = _which_or_fallback("ainl", "ainl")
    body = _ainl_run_wrapper_lines(ainl_exe)

    if dry_run:
        print(f"[dry-run] would create {target} (mode +x)")
        _log(verbose, body)
        return target

    zc_bin.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    mode = target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    target.chmod(mode)
    print(f"Installed wrapper: {target}")
    return target


def ensure_path_hint_in_shell_rc(*, home: Path, dry_run: bool, verbose: bool) -> list[str]:
    """Append ~/.zeroclaw/bin to PATH in ~/.bashrc and/or ~/.zshrc if missing."""
    notes: list[str] = []
    for name in (".bashrc", ".zshrc"):
        rc = home / name
        if not rc.is_file():
            continue
        text = rc.read_text(encoding="utf-8")
        if _PATH_LINE in text or ".zeroclaw/bin" in text:
            _log(verbose, f"PATH hint already present in {rc}")
            continue
        if dry_run:
            print(f"[dry-run] would append PATH line to {rc}")
            notes.append(str(rc))
            continue
        with rc.open("a", encoding="utf-8") as f:
            f.write("\n# Added by ainl install-zeroclaw\n")
            f.write(_PATH_LINE + "\n")
        print(f"Appended PATH line to {rc}")
        notes.append(str(rc))

    if not notes and not dry_run:
        print(
            "Tip: add ~/.zeroclaw/bin to PATH (e.g. add this line to ~/.bashrc or ~/.zshrc):\n"
            f"  {_PATH_LINE}"
        )
    elif dry_run and not notes:
        print(f"[dry-run] would suggest PATH line if no .bashrc/.zshrc update needed: {_PATH_LINE}")
    return notes


def run_install_zeroclaw(
    *,
    dry_run: bool,
    verbose: bool,
    home: Optional[Path] = None,
    run_pip: Optional[Callable[[bool], int]] = None,
) -> int:
    """
    Run full ZeroClaw bootstrap. When dry_run is True, no pip subprocess and no
    writes under home/.zeroclaw (or shell rc files).
    """
    home = home if home is not None else Path.home()
    pip_fn: Callable[[bool], int] = run_pip if run_pip is not None else default_run_pip_install

    if dry_run:
        print("[dry-run] would run: python -m pip install --upgrade 'ainl-lang[mcp]'")
    else:
        code = pip_fn(verbose)
        if code != 0:
            print(f"pip install failed with exit code {code}", file=sys.stderr)
            return code

    ensure_mcp_registration(home=home, dry_run=dry_run, verbose=verbose)
    ensure_ainl_run_wrapper(home=home, dry_run=dry_run, verbose=verbose)

    repo = detect_ainl_repo_root()
    if repo is not None:
        ensure_config_toml_ainl_bridge(home=home, repo_root=repo, dry_run=dry_run, verbose=verbose)
        ensure_zeroclaw_ainl_run_shim(home=home, repo_root=repo, dry_run=dry_run, verbose=verbose)
    else:
        print(
            "Tip: run `ainl install-zeroclaw` from your AI_Native_Lang git checkout to also "
            "install ~/.zeroclaw/config.toml [ainl_bridge] and ~/.zeroclaw/bin/zeroclaw-ainl-run.",
            file=sys.stderr,
        )

    ensure_path_hint_in_shell_rc(home=home, dry_run=dry_run, verbose=verbose)

    tip = 'Now say in ZeroClaw: "Import the morning briefing using AINL"'
    if dry_run:
        print(f"[dry-run] simulation finished (no changes). Without --dry-run: {tip}")
    else:
        print(f"AINL ZeroClaw bootstrap complete. {tip}")
    return 0


def run_install_zeroclaw_main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="ainl install-zeroclaw")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    ns = p.parse_args(argv)
    return run_install_zeroclaw(dry_run=ns.dry_run, verbose=ns.verbose)
