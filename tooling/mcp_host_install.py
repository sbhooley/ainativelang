"""Shared MCP host bootstrap for OpenClaw, ZeroClaw, Hermes Agent, and future stacks (pip, MCP config, ainl-run, PATH)."""

from __future__ import annotations

import argparse
import json
import shlex
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

PIP_SPEC = "ainativelang[mcp]"
MCP_SERVER_KEY = "ainl"
_WRAPPER_NAME = "ainl-run"


@dataclass(frozen=True)
class McpHostProfile:
    """One agent host that stores MCP config + bin shims under ~/.<dot_dir>/."""

    id: str
    dot_rel: Path
    config_filename: str
    config_kind: str  # "json_mcpServers" | "json_mcp_servers_under_mcp" | "yaml_mcp_servers" | "toml_mcp_servers_array"
    path_line: str
    path_marker: str
    success_tip: str


PROFILES: dict[str, McpHostProfile] = {
    "openclaw": McpHostProfile(
        id="openclaw",
        dot_rel=Path(".openclaw"),
        config_filename="openclaw.json",
        config_kind="json_mcp_servers_under_mcp",
        path_line='export PATH="$HOME/.openclaw/bin:$PATH"',
        path_marker=".openclaw/bin",
        success_tip='Now say in OpenClaw: "Import the morning briefing using AINL"',
    ),
    "zeroclaw": McpHostProfile(
        id="zeroclaw",
        dot_rel=Path(".zeroclaw"),
        config_filename="mcp.json",
        config_kind="json_mcpServers",
        path_line='export PATH="$HOME/.zeroclaw/bin:$PATH"',
        path_marker=".zeroclaw/bin",
        success_tip='Now say in ZeroClaw: "Import the morning briefing using AINL"',
    ),
    "hermes": McpHostProfile(
        id="hermes",
        dot_rel=Path(".hermes"),
        config_filename="config.yaml",
        config_kind="yaml_mcp_servers",
        path_line='export PATH="$HOME/.hermes/bin:$PATH"',
        path_marker=".hermes/bin",
        success_tip='Now say in Hermes: "Import the morning briefing using AINL" (or run: hermes chat)',
    ),
    "hermes-gateway": McpHostProfile(
        id="hermes-gateway",
        dot_rel=Path(".hermes"),
        config_filename="config.yaml",
        config_kind="yaml_mcp_servers",
        path_line='export PATH="$HOME/.hermes/bin:$PATH"',
        path_marker=".hermes/bin",
        success_tip='Now say in Hermes Gateway: "Import the morning briefing using AINL"',
    ),
    "armaraos": McpHostProfile(
        id="armaraos",
        dot_rel=Path(".armaraos"),
        config_filename="config.toml",
        config_kind="toml_mcp_servers_array",
        path_line='export PATH="$HOME/.armaraos/bin:$PATH"',
        path_marker=".armaraos/bin",
        success_tip=(
            "Now run: ainl status --host armaraos (then: ainl emit --target armaraos ...). "
            "Typical agents: set AINL_MCP_EXPOSURE_PROFILE=inspect_only in ~/.armaraos/.env "
            "(read-first tools + ainl://authoring-cheatsheet resource). Omit it for full MCP tool surface."
        ),
    ),
}

OPENCLAW_PROFILE = PROFILES["openclaw"]
ZEROCLAW_PROFILE = PROFILES["zeroclaw"]
ARMARAOS_PROFILE = PROFILES["armaraos"]


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
    """Merge AINL stdio MCP server into host config (idempotent by resolved command)."""
    host_dir = home / profile.dot_rel
    cfg_path = host_dir / profile.config_filename
    ainl_mcp = _which_or_fallback("ainl-mcp", "ainl-mcp")
    desired = {"command": ainl_mcp, "args": []}

    if profile.config_kind == "toml_mcp_servers_array":
        armaraos_mcp_env = (
            [
                "AINL_MCP_EXPOSURE_PROFILE",
                "AINL_MCP_TOOLS",
                "AINL_MCP_TOOLS_EXCLUDE",
                "AINL_MCP_RESOURCES",
                "AINL_MCP_RESOURCES_EXCLUDE",
            ]
            if profile.id == "armaraos"
            else None
        )
        _ensure_mcp_registration_toml_mcp_servers_array(
            cfg_path,
            server_key=MCP_SERVER_KEY,
            desired=desired,
            dry_run=dry_run,
            verbose=verbose,
            env_pass_through=armaraos_mcp_env,
        )
        # Transitional support: the upstream ArmaraOS/OpenFang fork currently uses ~/.openfang/config.toml.
        # We write/merge both locations so users can install AINL today and still be compatible after rebrand.
        if profile.id == "armaraos":
            legacy_cfg = home / ".openfang" / "config.toml"
            _ensure_mcp_registration_toml_mcp_servers_array(
                legacy_cfg,
                server_key=MCP_SERVER_KEY,
                desired=desired,
                dry_run=dry_run,
                verbose=verbose,
                env_pass_through=armaraos_mcp_env,
            )
        if not dry_run:
            print(f"Wrote MCP config: {cfg_path}")
            if profile.id == "armaraos":
                print(f"Wrote MCP config: {home / '.openfang' / 'config.toml'}")
        return

    if profile.config_kind == "yaml_mcp_servers":
        _ensure_mcp_registration_yaml_mcp_servers(
            cfg_path,
            server_key=MCP_SERVER_KEY,
            desired=desired,
            dry_run=dry_run,
            verbose=verbose,
        )
        if not dry_run:
            print(f"Wrote MCP config: {cfg_path}")
        return

    if profile.config_kind == "json_mcp_servers_under_mcp":
        _ensure_mcp_registration_json_under_mcp(
            cfg_path,
            server_key=MCP_SERVER_KEY,
            desired=desired,
            dry_run=dry_run,
            verbose=verbose,
        )
        if not dry_run:
            print(f"Wrote MCP config: {cfg_path}")
        return

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


def _ensure_mcp_registration_yaml_mcp_servers(
    cfg_path: Path,
    *,
    server_key: str,
    desired: dict,
    dry_run: bool,
    verbose: bool,
) -> None:
    """
    Hermes Agent uses ~/.hermes/config.yaml with a top-level `mcp_servers:` mapping.
    We do a minimal, idempotent text merge without a YAML dependency:
    - if `mcp_servers:` is absent, append a new block
    - if `mcp_servers:` exists and `ainl:` is already present under it, do nothing
    - otherwise, insert the `ainl:` block directly under `mcp_servers:`
    """
    desired_block = (
        "mcp_servers:\n"
        f"  {server_key}:\n"
        f"    command: \"{desired['command']}\"\n"
        "    args: []\n"
    )

    if not cfg_path.exists():
        if dry_run:
            print(f"[dry-run] would write {cfg_path} with mcp_servers.{server_key}")
            _log(verbose, desired_block)
            return
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(desired_block, encoding="utf-8")
        return

    text = cfg_path.read_text(encoding="utf-8")
    if "mcp_servers:" in text:
        # best-effort check: a server key under mcp_servers with two-space indent
        needle = f"\n  {server_key}:"
        if needle in text or text.lstrip().startswith(f"mcp_servers:\n  {server_key}:"):
            _log(verbose, f"MCP: {server_key!r} already registered in {cfg_path}")
            return

        lines = text.splitlines(keepends=True)
        out: list[str] = []
        inserted = False
        for i, line in enumerate(lines):
            out.append(line)
            if not inserted and line.strip() == "mcp_servers:":
                # Insert immediately after the key line.
                out.append(f"  {server_key}:\n")
                out.append(f"    command: \"{desired['command']}\"\n")
                out.append("    args: []\n")
                inserted = True
        if not inserted:
            # Fallback: append block (should be rare)
            out.append("\n" + desired_block if not text.endswith("\n") else desired_block)
        new_text = "".join(out)
    else:
        new_text = text
        if not new_text.endswith("\n"):
            new_text += "\n"
        new_text += "\n" + desired_block

    if dry_run:
        print(f"[dry-run] would update {cfg_path} with mcp_servers.{server_key}")
        _log(verbose, desired_block)
        return

    cfg_path.write_text(new_text, encoding="utf-8")


def _parse_toml_env_array_value(rhs: str) -> Optional[List[str]]:
    """Parse ``env = [ ... ]`` RHS as a list of strings (JSON-compatible)."""
    rhs = rhs.strip().rstrip(",")
    if not rhs.startswith("["):
        return None
    try:
        v = json.loads(rhs)
    except json.JSONDecodeError:
        try:
            v = json.loads(rhs.replace("'", '"'))
        except json.JSONDecodeError:
            return None
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return v
    return None


def _bracket_depth_delta(s: str) -> int:
    """Count ``[`` / ``]`` for TOML env var name lists (no brackets inside quoted names)."""
    return s.count("[") - s.count("]")


def _env_array_balanced_line_end(segment_body: List[str], env_idx: int) -> int:
    """First line index after the ``env = [ ... ]`` value where ``[``/``]`` brackets balance."""
    first = segment_body[env_idx]
    rhs = first.split("=", 1)[1] if "=" in first else ""
    depth = _bracket_depth_delta(rhs)
    end = env_idx + 1
    while depth > 0 and end < len(segment_body):
        depth += _bracket_depth_delta(segment_body[end])
        end += 1
    return end


def _skip_duplicate_env_tail_lines(segment_body: List[str], balanced_end: int) -> int:
    """
    Drop lines left behind when an older merge replaced only the first ``env`` line.

    Typical garbage: a stray ``]`` and/or quoted strings that belonged to the old multiline
    array body.
    """
    end = balanced_end
    while end < len(segment_body):
        s = segment_body[end].strip()
        if not s:
            end += 1
            continue
        if s == "]":
            end += 1
            continue
        if s.startswith('"') and (s.endswith(",") or s.endswith('"')):
            end += 1
            continue
        break
    return end


def _env_assignment_rhs_for_parse(segment_body: List[str], env_idx: int, balanced_end: int) -> str:
    """RHS of ``env = ...`` spanning ``[env_idx, balanced_end)`` (pretty-printed TOML safe)."""
    chunk = "".join(segment_body[env_idx:balanced_end])
    rhs = chunk.split("=", 1)[1].strip() if "=" in chunk else ""
    return rhs


def _merge_env_into_mcp_segment(
    segment_body: List[str],
    required: List[str],
) -> tuple[List[str], bool]:
    """Merge ``required`` env var names into the ``env =`` line of one ``[[mcp_servers]]`` body."""
    req = set(required)
    env_idx: Optional[int] = None
    for i, line in enumerate(segment_body):
        if line.strip().startswith("env = "):
            env_idx = i
            break
    if env_idx is not None:
        balanced_end = _env_array_balanced_line_end(segment_body, env_idx)
        rhs = _env_assignment_rhs_for_parse(segment_body, env_idx, balanced_end)
        cur = _parse_toml_env_array_value(rhs) or []
        union = sorted(set(cur) | req)
        remove_end = _skip_duplicate_env_tail_lines(segment_body, balanced_end)
        if union == sorted(cur) and remove_end == balanced_end:
            return segment_body, False
        old_first = segment_body[env_idx]
        body = f"env = {json.dumps(union)}"
        if old_first.endswith("\r\n"):
            new_line = body + "\r\n"
        elif old_first.endswith("\n"):
            new_line = body + "\n"
        else:
            new_line = body
        out = segment_body[:env_idx] + [new_line] + segment_body[remove_end:]
        return out, True

    insert_at = 0
    for i, line in enumerate(segment_body):
        if line.strip().startswith("timeout_secs"):
            insert_at = i + 1
        if line.strip().startswith("name = "):
            insert_at = i + 1
    union = sorted(req)
    new_line = f"env = {json.dumps(union)}\n"
    return segment_body[:insert_at] + [new_line] + segment_body[insert_at:], True


def _merge_mcp_env_pass_through_into_toml_text(
    text: str,
    server_key: str,
    required: List[str],
) -> tuple[str, bool]:
    """Scan TOML text for ``[[mcp_servers]]`` / ``name = server_key`` and merge ``env``."""
    if not required:
        return text, False
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    idx = 0
    changed = False
    while idx < len(lines):
        if lines[idx].strip() != "[[mcp_servers]]":
            out.append(lines[idx])
            idx += 1
            continue
        header = lines[idx]
        idx += 1
        segment_body: List[str] = []
        while idx < len(lines) and lines[idx].strip() != "[[mcp_servers]]":
            segment_body.append(lines[idx])
            idx += 1
        name_ok = any(
            f'name = "{server_key}"' in ln or f"name = '{server_key}'" in ln
            for ln in segment_body
        )
        if name_ok:
            new_body, seg_ch = _merge_env_into_mcp_segment(segment_body, required)
            changed = changed or seg_ch
            out.append(header)
            out.extend(new_body)
        else:
            out.append(header)
            out.extend(segment_body)
    return "".join(out), changed


def _ensure_mcp_registration_toml_mcp_servers_array(
    cfg_path: Path,
    *,
    server_key: str,
    desired: dict,
    dry_run: bool,
    verbose: bool,
    env_pass_through: Optional[List[str]] = None,
) -> None:
    """
    ArmaraOS config format: ~/.armaraos/config.toml with a top-level array:

      [[mcp_servers]]
      name = "ainl"
      command = "ainl-mcp"
      args = []

    We perform a minimal, idempotent text merge without a TOML parser:
    - if the file is missing, create it with the block
    - if any `name = "<server_key>"` exists and ``env_pass_through`` is set, merge
      those env var names into the existing ``env = [...]`` line (union, sorted)
    - if the server exists and no merge was needed, do nothing
    - otherwise append a new [[mcp_servers]] block at EOF
    """
    # OpenFang/ArmaraOS config schema expects a transport table under each entry.
    # See armaraos repo docs/configuration.md: [[mcp_servers]] + [mcp_servers.transport] type="stdio".
    env_list = env_pass_through if env_pass_through else []
    env_toml = json.dumps(env_list)
    desired_block = (
        "[[mcp_servers]]\n"
        f"name = \"{server_key}\"\n"
        "timeout_secs = 30\n"
        f"env = {env_toml}\n"
        "\n"
        "[mcp_servers.transport]\n"
        "type = \"stdio\"\n"
        f"command = \"{desired['command']}\"\n"
        "args = []\n"
    )

    if not cfg_path.exists():
        if dry_run:
            print(f"[dry-run] would write {cfg_path} with mcp_servers {server_key}")
            _log(verbose, desired_block)
            return
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(desired_block, encoding="utf-8")
        return

    text = cfg_path.read_text(encoding="utf-8", errors="replace")
    # Idempotency: accept either name-only legacy blocks or the transport-style blocks.
    needle = f"name = \"{server_key}\""
    if needle in text:
        if env_pass_through:
            new_text, did = _merge_mcp_env_pass_through_into_toml_text(
                text, server_key, env_pass_through
            )
            if did:
                if dry_run:
                    print(
                        f"[dry-run] would merge MCP env pass-through for {server_key!r} in {cfg_path}"
                    )
                    _log(verbose, new_text)
                    return
                cfg_path.write_text(new_text, encoding="utf-8")
                _log(
                    verbose,
                    f"MCP: merged env pass-through for {server_key!r} in {cfg_path}",
                )
                return
        _log(
            verbose,
            f"MCP: {server_key!r} already registered in {cfg_path} (toml [[mcp_servers]])",
        )
        return

    new_text = text
    if not new_text.endswith("\n"):
        new_text += "\n"
    if not new_text.endswith("\n\n"):
        new_text += "\n"
    new_text += desired_block

    if dry_run:
        print(f"[dry-run] would append [[mcp_servers]] block to {cfg_path} for {server_key}")
        _log(verbose, desired_block)
        return

    cfg_path.write_text(new_text, encoding="utf-8")


def _ensure_mcp_registration_json_under_mcp(
    cfg_path: Path,
    *,
    server_key: str,
    desired: dict,
    dry_run: bool,
    verbose: bool,
) -> None:
    """
    OpenClaw format: openclaw.json with top-level "mcp" containing "servers" mapping.
    Writes/merges: {"mcp": {"servers": {"ainl": {"command": "...", "args": []}}}}
    """
    server_block = {server_key: desired}

    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    if not isinstance(data, dict):
        data = {}

    # Compatibility: if a legacy top-level mcpServers mapping already has this
    # server registered with the same command, keep the file unchanged.
    legacy_servers = data.get("mcpServers")
    if isinstance(legacy_servers, dict):
        legacy_existing = legacy_servers.get(server_key)
        if isinstance(legacy_existing, dict) and legacy_existing.get("command") == desired["command"]:
            _log(verbose, f"MCP: {server_key!r} already registered in {cfg_path} under legacy mcpServers")
            return

    # Ensure "mcp" exists and is a dict
    mcp = data.get("mcp")
    if mcp is None or not isinstance(mcp, dict):
        mcp = {}
        data["mcp"] = mcp

    # Ensure "servers" exists under mcp
    servers = mcp.get("servers")
    if servers is None or not isinstance(servers, dict):
        servers = {}
        mcp["servers"] = servers

    # Check if already present with same command
    existing = servers.get(server_key)
    if isinstance(existing, dict) and existing.get("command") == desired["command"]:
        _log(verbose, f"MCP: {server_key!r} already registered in {cfg_path} under mcp.servers")
        return

    servers[server_key] = desired

    if dry_run:
        print(f"[dry-run] would write/update {cfg_path} with mcp.servers.{server_key}")
        _log(verbose, json.dumps({"mcp": {"servers": {server_key: desired}}}, indent=2))
        return

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
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

    if hid.startswith("hermes"):
        _warn_if_hermes_missing(home=home, dry_run=dry_run, verbose=verbose)

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
    if hid.startswith("hermes"):
        _run_skills_hermes_install(home=home, dry_run=dry_run, verbose=verbose, log=_log)

    tip = profile.success_tip
    if dry_run:
        print(f"[dry-run] simulation finished (no changes). Without --dry-run: {tip}")
    else:
        print(f"AINL {profile.id} MCP bootstrap complete. {tip}")
    return 0


def _warn_if_hermes_missing(*, home: Path, dry_run: bool, verbose: bool) -> None:
    from shutil import which

    cfg_json = home / ".hermes" / "config.json"
    cfg_yaml = home / ".hermes" / "config.yaml"
    hermes_exe = which("hermes")
    if hermes_exe or cfg_json.exists() or cfg_yaml.exists():
        _log(verbose, "Hermes detection: found hermes CLI or ~/.hermes config")
        return
    msg = "Hermes detection: hermes not found on PATH and ~/.hermes/config.{json,yaml} missing"
    if dry_run:
        print(f"[dry-run] {msg}")
    else:
        print(f"Warning: {msg}", file=sys.stderr)


def _run_skills_hermes_install(*, home: Path, dry_run: bool, verbose: bool, log: Callable[[bool, str], None]) -> None:
    """
    Hermes install additionally runs skills/hermes/install.sh from this repo if present.
    This mirrors the OpenClaw skill pack flow, but the CLI triggers it automatically.
    """
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "skills" / "hermes" / "install.sh"
    if not script.is_file():
        if dry_run:
            print(f"[dry-run] would run skills/hermes/install.sh if present at {script}")
        else:
            print(
                "Tip: skills/hermes/install.sh not found in this checkout; install Hermes skill pack by "
                "updating to a repo version that includes skills/hermes/",
                file=sys.stderr,
            )
        return

    env = dict(**{"AINL_HERMES_INSTALL_MCP_ALREADY": "1"}, **{})
    cmd = ["bash", str(script)]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(shlex.quote(c) for c in cmd)}")
        return
    log(verbose, "+ " + " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd, check=False, env={**env, **dict(**{})})
    if proc.returncode != 0:
        print(f"Warning: skills/hermes/install.sh failed (exit={proc.returncode})", file=sys.stderr)


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
