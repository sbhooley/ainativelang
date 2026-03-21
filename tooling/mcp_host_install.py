"""Shared MCP host bootstrap for OpenClaw, ZeroClaw, and future stacks (pip, mcpServers.ainl, ainl-run, PATH)."""

from __future__ import annotations

import argparse
import json
import shlex
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

PIP_SPEC = "ainl-lang[mcp]"
MCP_SERVER_KEY = "ainl"
_WRAPPER_NAME = "ainl-run"


@dataclass(frozen=True)
class McpHostProfile:
    """One agent host that stores MCP config + bin shims under ~/.<dot_dir>/."""

    id: str
    dot_rel: Path
    config_filename: str
    path_line: str
    path_marker: str
    success_tip: str


PROFILES: dict[str, McpHostProfile] = {
    "openclaw": McpHostProfile(
        id="openclaw",
        dot_rel=Path(".openclaw"),
        config_filename="openclaw.json",
        path_line='export PATH="$HOME/.openclaw/bin:$PATH"',
        path_marker=".openclaw/bin",
        success_tip='Now say in OpenClaw: "Import the morning briefing using AINL"',
    ),
    "zeroclaw": McpHostProfile(
        id="zeroclaw",
        dot_rel=Path(".zeroclaw"),
        config_filename="mcp.json",
        path_line='export PATH="$HOME/.zeroclaw/bin:$PATH"',
        path_marker=".zeroclaw/bin",
        success_tip='Now say in ZeroClaw: "Import the morning briefing using AINL"',
    ),
}

OPENCLAW_PROFILE = PROFILES["openclaw"]
ZEROCLAW_PROFILE = PROFILES["zeroclaw"]


def list_mcp_host_ids() -> tuple[str, ...]:
    return tuple(sorted(PROFILES.keys()))


def _log(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def default_run_pip_install(verbose: bool) -> int:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PIP_SPEC]
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
    profile: McpHostProfile,
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Merge AINL stdio MCP server into host JSON config (idempotent by resolved command)."""
    host_dir = home / profile.dot_rel
    cfg_path = host_dir / profile.config_filename
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

    existing = servers.get(MCP_SERVER_KEY)
    if isinstance(existing, dict) and existing.get("command") == desired["command"]:
        _log(verbose, f"MCP: {MCP_SERVER_KEY!r} already registered in {cfg_path}")
        return

    servers[MCP_SERVER_KEY] = desired
    data["mcpServers"] = servers

    if dry_run:
        print(f"[dry-run] would write/update {cfg_path} with mcpServers.{MCP_SERVER_KEY}")
        _log(verbose, json.dumps({"mcpServers": {MCP_SERVER_KEY: desired}}, indent=2))
        return

    host_dir.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote MCP config: {cfg_path}")


def ensure_ainl_run_wrapper(
    profile: McpHostProfile,
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> Path:
    bin_dir = home / profile.dot_rel / "bin"
    target = bin_dir / _WRAPPER_NAME
    ainl_exe = _which_or_fallback("ainl", "ainl")
    body = _ainl_run_wrapper_lines(ainl_exe)

    if dry_run:
        print(f"[dry-run] would create {target} (mode +x)")
        _log(verbose, body)
        return target

    bin_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    mode = target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    target.chmod(mode)
    print(f"Installed wrapper: {target}")
    return target


def ensure_path_hint_in_shell_rc(
    profile: McpHostProfile,
    *,
    home: Path,
    dry_run: bool,
    verbose: bool,
) -> list[str]:
    """Append host bin dir to PATH in ~/.bashrc and/or ~/.zshrc if missing."""
    notes: list[str] = []
    tag = f"ainl install-mcp --host {profile.id}"
    for name in (".bashrc", ".zshrc"):
        rc = home / name
        if not rc.is_file():
            continue
        text = rc.read_text(encoding="utf-8")
        if profile.path_line in text or profile.path_marker in text:
            _log(verbose, f"PATH hint already present in {rc}")
            continue
        if dry_run:
            print(f"[dry-run] would append PATH line to {rc}")
            notes.append(str(rc))
            continue
        with rc.open("a", encoding="utf-8") as f:
            f.write(f"\n# Added by {tag}\n")
            f.write(profile.path_line + "\n")
        print(f"Appended PATH line to {rc}")
        notes.append(str(rc))

    if not notes and not dry_run:
        print(
            f"Tip: add ~/{profile.dot_rel}/bin to PATH (e.g. add this line to ~/.bashrc or ~/.zshrc):\n"
            f"  {profile.path_line}"
        )
    elif dry_run and not notes:
        print(f"[dry-run] would suggest PATH line if no .bashrc/.zshrc update needed: {profile.path_line}")
    return notes


def run_install_mcp_host(
    host_id: str,
    *,
    dry_run: bool,
    verbose: bool,
    home: Optional[Path] = None,
    run_pip: Optional[Callable[[bool], int]] = None,
) -> int:
    """
    Run full bootstrap for a known MCP host. When dry_run is True, no pip subprocess
    and no writes under home/(dot dir) or shell rc files.
    """
    hid = host_id.strip().lower()
    if hid not in PROFILES:
        print(f"Unknown host {host_id!r}. Choose one of: {', '.join(PROFILES)}", file=sys.stderr)
        return 2

    profile = PROFILES[hid]
    home = home if home is not None else Path.home()
    pip_fn: Callable[[bool], int] = run_pip if run_pip is not None else default_run_pip_install

    if dry_run:
        print(f"[dry-run] would run: python -m pip install --upgrade '{PIP_SPEC}'")
    else:
        code = pip_fn(verbose)
        if code != 0:
            print(f"pip install failed with exit code {code}", file=sys.stderr)
            return code

    ensure_mcp_registration(profile, home=home, dry_run=dry_run, verbose=verbose)
    ensure_ainl_run_wrapper(profile, home=home, dry_run=dry_run, verbose=verbose)

    if hid == "zeroclaw":
        from tooling.zeroclaw_bridge import (
            detect_ainl_repo_root,
            ensure_config_toml_ainl_bridge,
            ensure_zeroclaw_ainl_run_shim,
        )

        repo = detect_ainl_repo_root()
        if repo is not None:
            ensure_config_toml_ainl_bridge(home=home, repo_root=repo, dry_run=dry_run, verbose=verbose, log=_log)
            ensure_zeroclaw_ainl_run_shim(home=home, repo_root=repo, dry_run=dry_run, verbose=verbose, log=_log)
        else:
            print(
                "Tip: run `ainl install-mcp --host zeroclaw` from your AI_Native_Lang git checkout to also "
                "install ~/.zeroclaw/config.toml [ainl_bridge] and ~/.zeroclaw/bin/zeroclaw-ainl-run.",
                file=sys.stderr,
            )

    ensure_path_hint_in_shell_rc(profile, home=home, dry_run=dry_run, verbose=verbose)

    tip = profile.success_tip
    if dry_run:
        print(f"[dry-run] simulation finished (no changes). Without --dry-run: {tip}")
    else:
        print(f"AINL {profile.id} MCP bootstrap complete. {tip}")
    return 0


def run_install_mcp_main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="ainl install-mcp",
        description="Bootstrap AINL MCP + ainl-run for OpenClaw, ZeroClaw, or future hosts.",
    )
    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument(
        "--host",
        choices=list_mcp_host_ids(),
        help="Agent stack (add new ids in tooling/mcp_host_install.PROFILES)",
    )
    mx.add_argument(
        "--list-hosts",
        action="store_true",
        help="Print known host ids and exit",
    )
    p.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    p.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    ns = p.parse_args(argv)
    if ns.list_hosts:
        print(" ".join(list_mcp_host_ids()))
        return 0
    return run_install_mcp_host(ns.host, dry_run=ns.dry_run, verbose=ns.verbose)
