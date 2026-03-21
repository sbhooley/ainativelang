"""Bootstrap AINL for OpenClaw: pip upgrade, MCP merge in openclaw.json, ainl-run wrapper, PATH hints."""

from __future__ import annotations

import json
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

_OC_REL = Path(".openclaw")
_CONFIG_NAME = "openclaw.json"
_WRAPPER_NAME = "ainl-run"
_PATH_LINE = 'export PATH="$HOME/.openclaw/bin:$PATH"'
_MCP_SERVER_KEY = "ainl"


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
    """Merge AINL stdio MCP server into ~/.openclaw/openclaw.json (idempotent by command)."""
    oc = home / _OC_REL
    cfg_path = oc / _CONFIG_NAME
    ainl_mcp = _which_or_fallback("ainl-mcp", "ainl-mcp")

    desired = {"command": ainl_mcp, "args": []}

    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
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
        _log(verbose, f"MCP: {_MCP_SERVER_KEY!r} already registered in {cfg_path}")
        return

    servers[_MCP_SERVER_KEY] = desired
    data["mcpServers"] = servers

    if dry_run:
        print(f"[dry-run] would write/update {cfg_path} with mcpServers.{_MCP_SERVER_KEY}")
        _log(verbose, json.dumps({"mcpServers": {_MCP_SERVER_KEY: desired}}, indent=2))
        return

    oc.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote MCP config: {cfg_path}")


def ensure_ainl_run_wrapper(
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> Path:
    oc_bin = home / _OC_REL / "bin"
    target = oc_bin / _WRAPPER_NAME
    ainl_exe = _which_or_fallback("ainl", "ainl")
    body = _ainl_run_wrapper_lines(ainl_exe)

    if dry_run:
        print(f"[dry-run] would create {target} (mode +x)")
        _log(verbose, body)
        return target

    oc_bin.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    mode = target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    target.chmod(mode)
    print(f"Installed wrapper: {target}")
    return target


def ensure_path_hint_in_shell_rc(*, home: Path, dry_run: bool, verbose: bool) -> list[str]:
    """Append ~/.openclaw/bin to PATH in ~/.bashrc and/or ~/.zshrc if missing."""
    notes: list[str] = []
    for name in (".bashrc", ".zshrc"):
        rc = home / name
        if not rc.is_file():
            continue
        text = rc.read_text(encoding="utf-8")
        if _PATH_LINE in text or ".openclaw/bin" in text:
            _log(verbose, f"PATH hint already present in {rc}")
            continue
        if dry_run:
            print(f"[dry-run] would append PATH line to {rc}")
            notes.append(str(rc))
            continue
        with rc.open("a", encoding="utf-8") as f:
            f.write("\n# Added by ainl install-openclaw\n")
            f.write(_PATH_LINE + "\n")
        print(f"Appended PATH line to {rc}")
        notes.append(str(rc))

    if not notes and not dry_run:
        print(
            "Tip: add ~/.openclaw/bin to PATH (e.g. add this line to ~/.bashrc or ~/.zshrc):\n"
            f"  {_PATH_LINE}"
        )
    elif dry_run and not notes:
        print(f"[dry-run] would suggest PATH line if no .bashrc/.zshrc update needed: {_PATH_LINE}")
    return notes


def run_install_openclaw(
    *,
    dry_run: bool,
    verbose: bool,
    home: Optional[Path] = None,
    run_pip: Optional[Callable[[bool], int]] = None,
) -> int:
    """
    Run full OpenClaw bootstrap. When dry_run is True, no pip subprocess and no
    writes under home/.openclaw (or shell rc files).
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
    ensure_path_hint_in_shell_rc(home=home, dry_run=dry_run, verbose=verbose)

    tip = 'Now say in OpenClaw: "Import the morning briefing using AINL"'
    if dry_run:
        print(f"[dry-run] simulation finished (no changes). Without --dry-run: {tip}")
    else:
        print(f"AINL OpenClaw bootstrap complete. {tip}")
    return 0


def run_install_openclaw_main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="ainl install-openclaw")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    ns = p.parse_args(argv)
    return run_install_openclaw(dry_run=ns.dry_run, verbose=ns.verbose)
