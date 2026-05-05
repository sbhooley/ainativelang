"""One-step agent install: detect host(s), write MCP config, verify.

This module powers ``ainl setup`` (also reachable as
``python -m ainativelang setup``). It auto-detects which agent hosts are
present on the system and registers AINL's stdio MCP server with each:

- Claude Code (project-level via ``./.mcp.json``, user-level via ``~/.claude/mcp.json``)
- Cursor (``~/.cursor/mcp.json``)
- Cline (``~/Library/Application Support/Cline/...`` on macOS, etc.)
- Codex CLI (``~/.codex/config.toml`` ``[mcp_servers.<name>]`` table)
- Codex Desktop (``~/Library/Application Support/Codex/config.json`` and platform equivalents)
- Claude Desktop (``~/Library/Application Support/Claude/claude_desktop_config.json`` and platform equivalents)

For OpenClaw / Hermes / ArmaraOS, we delegate to the existing
``ainl install-mcp --host <name>`` infrastructure rather than duplicating its
host-specific quirks.

Design contract: see ``docs/architecture/2026-05-05-agent-install-simplification.md``.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

MCP_SERVER_NAME = "ainl"
MCP_BIN_NAME = "ainl-mcp"


@dataclass(frozen=True)
class DetectedHost:
    """One host found on the system (or the generic-MCP fallback)."""

    kind: str  # stable id, e.g. "claude-code-project", "cursor", "codex-cli"
    config_path: Optional[Path]  # None for delegated hosts and generic-mcp
    delegate_host: Optional[str] = None  # legacy host id for ainl install-mcp delegation
    note: str = ""  # human-readable detection signal description


@dataclass
class WriteResult:
    kind: str
    config_path: Optional[Path]
    action: str  # "written" | "delegated" | "skipped" | "printed" | "dry-run"
    detail: str = ""
    backup_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Host detection
# ---------------------------------------------------------------------------


def _macos_app_support(home: Path) -> Path:
    return home / "Library" / "Application Support"


def _appdata_dir(env: Optional[dict[str, str]] = None) -> Optional[Path]:
    env = env if env is not None else os.environ
    raw = env.get("APPDATA")
    return Path(raw) if raw else None


def _xdg_config_home(home: Path, env: Optional[dict[str, str]] = None) -> Path:
    env = env if env is not None else os.environ
    raw = env.get("XDG_CONFIG_HOME")
    return Path(raw) if raw else home / ".config"


def detect_hosts(
    *,
    home: Path,
    cwd: Path,
    system: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> list[DetectedHost]:
    """Return every host that's present. Order is stable for deterministic output."""

    system = system or platform.system()
    env = env if env is not None else os.environ
    found: list[DetectedHost] = []

    # Claude Code project-level config — most specific, most likely to be the
    # caller's intent when an agent is running inside an IDE checkout.
    if (cwd / ".mcp.json").exists() or (cwd / ".claude").is_dir():
        found.append(
            DetectedHost(
                kind="claude-code-project",
                config_path=cwd / ".mcp.json",
                note=f"detected .mcp.json or .claude/ in cwd ({cwd})",
            )
        )

    # Claude Code user-level
    if (home / ".claude").is_dir():
        found.append(
            DetectedHost(
                kind="claude-code-user",
                config_path=home / ".claude" / "mcp.json",
                note=f"detected {home}/.claude/",
            )
        )

    # Cursor
    cursor_path = home / ".cursor" / "mcp.json"
    if cursor_path.exists() or (home / ".cursor").is_dir() or any(
        k.startswith("CURSOR_") for k in env
    ):
        found.append(
            DetectedHost(
                kind="cursor",
                config_path=cursor_path,
                note="detected ~/.cursor/ or CURSOR_* env",
            )
        )

    # Cline
    cline_dir: Optional[Path] = None
    if system == "Darwin":
        cline_dir = _macos_app_support(home) / "Cline"
    elif system == "Windows":
        appdata = _appdata_dir(env)
        if appdata:
            cline_dir = appdata / "Cline"
    else:
        cline_dir = _xdg_config_home(home, env) / "Cline"
    if cline_dir is not None and cline_dir.is_dir():
        found.append(
            DetectedHost(
                kind="cline",
                config_path=cline_dir / "cline_mcp_settings.json",
                note=f"detected {cline_dir}",
            )
        )

    # Codex CLI
    codex_cli_dir = home / ".codex"
    # Use env-provided PATH so tests can isolate detection from the real shell.
    # shutil.which(path=None) falls back to os.environ['PATH'], so when env was
    # supplied without a PATH key, pass empty string explicitly (= no lookup).
    _path_for_which = env.get("PATH", "")
    codex_on_path = bool(shutil.which("codex", path=_path_for_which))
    if codex_cli_dir.is_dir() or codex_on_path:
        found.append(
            DetectedHost(
                kind="codex-cli",
                config_path=codex_cli_dir / "config.toml",
                note="detected ~/.codex/ or `codex` on PATH",
            )
        )

    # Codex Desktop
    codex_desktop_path: Optional[Path] = None
    if system == "Darwin":
        codex_desktop_path = _macos_app_support(home) / "Codex" / "config.json"
    elif system == "Windows":
        appdata = _appdata_dir(env)
        if appdata:
            codex_desktop_path = appdata / "Codex" / "config.json"
    if codex_desktop_path is not None and codex_desktop_path.exists():
        found.append(
            DetectedHost(
                kind="codex-desktop",
                config_path=codex_desktop_path,
                note=f"detected {codex_desktop_path}",
            )
        )

    # Claude Desktop
    claude_desktop_path: Optional[Path] = None
    if system == "Darwin":
        claude_desktop_path = (
            _macos_app_support(home) / "Claude" / "claude_desktop_config.json"
        )
    elif system == "Windows":
        appdata = _appdata_dir(env)
        if appdata:
            claude_desktop_path = appdata / "Claude" / "claude_desktop_config.json"
    if claude_desktop_path is not None and claude_desktop_path.exists():
        found.append(
            DetectedHost(
                kind="claude-desktop",
                config_path=claude_desktop_path,
                note=f"detected {claude_desktop_path}",
            )
        )

    # OpenClaw / Hermes / ArmaraOS — delegate to existing `install-mcp --host`
    if (home / ".openclaw" / "openclaw.json").exists():
        found.append(
            DetectedHost(
                kind="openclaw",
                config_path=None,
                delegate_host="openclaw",
                note=f"detected {home}/.openclaw/openclaw.json",
            )
        )
    if (home / ".hermes").is_dir():
        found.append(
            DetectedHost(
                kind="hermes",
                config_path=None,
                delegate_host="hermes",
                note=f"detected {home}/.hermes/",
            )
        )
    if (home / ".armaraos" / "config.toml").exists():
        found.append(
            DetectedHost(
                kind="armaraos",
                config_path=None,
                delegate_host="armaraos",
                note=f"detected {home}/.armaraos/config.toml",
            )
        )

    return found


# ---------------------------------------------------------------------------
# Config writers
# ---------------------------------------------------------------------------


def resolve_ainl_mcp_command(*, prefer: Optional[str] = None) -> str:
    """Resolve ainl-mcp to an absolute path so GUI MCP hosts can find it.

    GUI hosts (Claude Desktop, Cursor on macOS) launch their MCP servers from
    a context that often does not include ``~/.local/bin`` or virtualenv bin
    dirs in PATH, so a bare ``ainl-mcp`` produces a silent boot failure.
    Always emit an absolute path.
    """
    if prefer:
        p = Path(prefer)
        if p.is_absolute():
            return str(p)
    found = shutil.which(MCP_BIN_NAME)
    if found:
        return found
    # Best-effort: sys.prefix/bin or sys.prefix/Scripts for Windows
    candidates = [
        Path(sys.prefix) / "bin" / MCP_BIN_NAME,
        Path(sys.prefix) / "Scripts" / (MCP_BIN_NAME + ".exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Fall back to the bare name; setup will warn the user.
    return MCP_BIN_NAME


def _utc_compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _atomic_write(path: Path, content: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _backup(path: Path, *, dry_run: bool) -> Optional[Path]:
    if not path.exists() or dry_run:
        return None
    bak = path.with_name(f"{path.name}.ainl-backup-{_utc_compact_timestamp()}")
    shutil.copy2(path, bak)
    return bak


def _server_entry(command: str, env: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {"command": command, "args": []}
    if env:
        out["env"] = dict(env)
    return out


def write_json_mcpservers(
    path: Path,
    *,
    server_name: str,
    command: str,
    env: dict[str, str],
    dry_run: bool,
    container_key: str = "mcpServers",
) -> WriteResult:
    """Merge the ainl entry into a JSON config under ``container_key``.

    Used by Claude Code (project + user), Cursor, Cline, Claude Desktop,
    Codex Desktop. They all share the same ``mcpServers: {<name>: {...}}``
    shape — only the file path differs.
    """
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8") or "{}")
            if not isinstance(existing, dict):
                existing = {}
        except json.JSONDecodeError:
            existing = {}
    container = existing.setdefault(container_key, {})
    if not isinstance(container, dict):
        # Some hosts may use a list; rebuild as dict for our supported shape.
        container = {}
        existing[container_key] = container
    container[server_name] = _server_entry(command, env)
    backup = _backup(path, dry_run=dry_run)
    new_content = json.dumps(existing, indent=2, sort_keys=True) + "\n"
    _atomic_write(path, new_content, dry_run=dry_run)
    return WriteResult(
        kind="json_mcpServers",
        config_path=path,
        action="dry-run" if dry_run else "written",
        detail=f"merged {server_name} into {container_key}",
        backup_path=backup,
    )


def write_codex_cli_toml(
    path: Path,
    *,
    server_name: str,
    command: str,
    env: dict[str, str],
    dry_run: bool,
    cwd_value: Optional[str] = None,
) -> WriteResult:
    """Merge ``[mcp_servers.<server_name>]`` into Codex CLI's TOML config.

    The Codex config file has many sections (model, projects, plugins, ...).
    We only touch the mcp_servers table for our entry. We cannot use a real
    TOML library for write because tomllib is read-only on stdlib; we do a
    targeted text-level merge.
    """
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    backup = _backup(path, dry_run=dry_run)
    new_text = _merge_codex_cli_toml_block(
        existing_text,
        server_name=server_name,
        command=command,
        env=env,
        cwd_value=cwd_value,
    )
    _atomic_write(path, new_text, dry_run=dry_run)
    if not dry_run and tomllib is not None and path.exists():
        # Defensive: fail loudly if our merge produced invalid TOML.
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - safety net
            raise RuntimeError(f"Wrote invalid TOML to {path}: {exc}") from exc
    return WriteResult(
        kind="toml_codex_cli",
        config_path=path,
        action="dry-run" if dry_run else "written",
        detail=f"merged [mcp_servers.{server_name}]",
        backup_path=backup,
    )


def _merge_codex_cli_toml_block(
    existing_text: str,
    *,
    server_name: str,
    command: str,
    env: dict[str, str],
    cwd_value: Optional[str],
) -> str:
    """Replace any existing ``[mcp_servers.<server_name>]`` block, or append one.

    Targeted text merge: we don't reformat unrelated sections of the config.
    """
    lines = existing_text.splitlines(keepends=False)
    header = f"[mcp_servers.{server_name}]"
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == header:
            start_idx = i
            continue
        if start_idx is not None and stripped.startswith("[") and stripped.endswith("]"):
            end_idx = i
            break
    if start_idx is not None and end_idx is None:
        end_idx = len(lines)
    block_lines = [header, f'command = "{_escape_toml(command)}"']
    if cwd_value:
        block_lines.append(f'cwd = "{_escape_toml(cwd_value)}"')
    block_lines.append("enabled = true")
    if env:
        env_pairs = ", ".join(
            f'{_toml_key(k)} = "{_escape_toml(v)}"' for k, v in sorted(env.items())
        )
        block_lines.append(f"env = {{ {env_pairs} }}")
    new_block = "\n".join(block_lines)
    if start_idx is not None and end_idx is not None:
        # Replace existing block, preserve surrounding content
        before = lines[:start_idx]
        after = lines[end_idx:]
        merged = before + [new_block] + ([""] if after and after[0].strip() else []) + after
        return "\n".join(merged) + ("\n" if not existing_text.endswith("\n") else "")
    # Append a new block
    sep = "" if not existing_text or existing_text.endswith("\n\n") else (
        "\n" if existing_text.endswith("\n") else "\n\n"
    )
    return existing_text + sep + new_block + "\n"


def _escape_toml(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _toml_key(s: str) -> str:
    """Bare keys must match [A-Za-z0-9_-]+; otherwise quote."""
    if s and all(c.isalnum() or c in "_-" for c in s):
        return s
    return f'"{_escape_toml(s)}"'


# ---------------------------------------------------------------------------
# Generic MCP fallback (print-only)
# ---------------------------------------------------------------------------


def render_generic_mcp_block(*, command: str, env: dict[str, str]) -> str:
    """Emit a copy-pasteable stdio MCP server entry for any host.

    Hosts not auto-detected can paste this into their MCP config.
    """
    block = {
        "mcpServers": {
            MCP_SERVER_NAME: _server_entry(command, env),
        }
    }
    return json.dumps(block, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


HOST_KINDS_DIRECT: tuple[str, ...] = (
    "claude-code-project",
    "claude-code-user",
    "cursor",
    "cline",
    "codex-cli",
    "codex-desktop",
    "claude-desktop",
)
HOST_KINDS_DELEGATED: tuple[str, ...] = ("openclaw", "hermes", "armaraos")


def _agent_id_for_host(kind: str) -> str:
    return f"ainl-via-{kind}"


def _env_for_host(kind: str, base_env: dict[str, str]) -> dict[str, str]:
    out = {"AINL_MCP_AGENT_ID": _agent_id_for_host(kind)}
    profile = base_env.get("AINL_MCP_EXPOSURE_PROFILE")
    if profile:
        out["AINL_MCP_EXPOSURE_PROFILE"] = profile
    return out


def configure_host(
    host: DetectedHost,
    *,
    command: str,
    env: dict[str, str],
    dry_run: bool,
    home: Path,
    delegate: Optional[Callable[[str, bool, bool], int]] = None,
    verbose: bool = False,
) -> WriteResult:
    """Configure one host. Direct hosts get a JSON or TOML write; delegated
    hosts call into ``ainl install-mcp --host <name>``."""
    if host.delegate_host:
        if delegate is None or dry_run:
            return WriteResult(
                kind=host.kind,
                config_path=None,
                action="dry-run" if dry_run else "skipped",
                detail=f"would delegate to ainl install-mcp --host {host.delegate_host}",
            )
        rc = delegate(host.delegate_host, dry_run, verbose)
        return WriteResult(
            kind=host.kind,
            config_path=None,
            action="delegated",
            detail=f"ainl install-mcp --host {host.delegate_host} → rc={rc}",
        )
    if host.config_path is None:
        return WriteResult(
            kind=host.kind,
            config_path=None,
            action="skipped",
            detail="no config path resolved",
        )
    if host.kind == "codex-cli":
        result = write_codex_cli_toml(
            host.config_path,
            server_name=MCP_SERVER_NAME,
            command=command,
            env=env,
            dry_run=dry_run,
            cwd_value=str(home),
        )
    else:
        result = write_json_mcpservers(
            host.config_path,
            server_name=MCP_SERVER_NAME,
            command=command,
            env=env,
            dry_run=dry_run,
        )
    # Surface the host kind in summaries; preserve the writer's other fields.
    return WriteResult(
        kind=host.kind,
        config_path=result.config_path,
        action=result.action,
        detail=result.detail,
        backup_path=result.backup_path,
    )


def run_setup(
    *,
    home: Optional[Path] = None,
    cwd: Optional[Path] = None,
    target_host: Optional[str] = None,
    dry_run: bool = False,
    no_verify: bool = False,
    print_config_only: bool = False,
    verbose: bool = False,
    out: Any = sys.stdout,
    err: Any = sys.stderr,
    delegate: Optional[Callable[[str, bool, bool], int]] = None,
    env: Optional[dict[str, str]] = None,
    system: Optional[str] = None,
) -> int:
    """Main entry. Returns 0 on success, non-zero on failure.

    - ``target_host``: if set, bypass detection and configure exactly that host.
    - ``print_config_only``: don't touch any files; print stdio config block.
    - ``dry_run``: print what would change, write nothing.
    """
    home = home or Path.home()
    cwd = cwd or Path.cwd()
    base_env = env if env is not None else dict(os.environ)
    command = resolve_ainl_mcp_command()

    if print_config_only:
        env = _env_for_host("generic", base_env)
        out.write(render_generic_mcp_block(command=command, env=env))
        return 0

    if target_host:
        # Forced single host
        synthetic = _synthesize_host(target_host, home=home, cwd=cwd)
        if synthetic is None:
            err.write(
                f"unknown host {target_host!r}; supported: "
                + ", ".join(HOST_KINDS_DIRECT + HOST_KINDS_DELEGATED + ("generic-mcp",))
                + "\n"
            )
            return 2
        hosts = [synthetic]
    else:
        hosts = detect_hosts(home=home, cwd=cwd, system=system, env=base_env)

    if not hosts:
        err.write(
            "no host detected; printing the generic stdio MCP config block "
            "for paste-into-host scenarios.\n\n"
        )
        env = _env_for_host("generic", base_env)
        out.write(render_generic_mcp_block(command=command, env=env))
        err.write(
            f"\nadd that to your host's MCP config (the {MCP_SERVER_NAME} key under "
            f"mcpServers). re-run `ainl setup` afterwards to verify.\n"
        )
        return 0

    results: list[WriteResult] = []
    for host in hosts:
        env = _env_for_host(host.kind, base_env)
        try:
            result = configure_host(
                host,
                command=command,
                env=env,
                dry_run=dry_run,
                home=home,
                delegate=delegate,
                verbose=verbose,
            )
        except Exception as exc:  # pragma: no cover - defensive
            err.write(f"[{host.kind}] FAILED: {exc}\n")
            results.append(
                WriteResult(
                    kind=host.kind,
                    config_path=host.config_path,
                    action="error",
                    detail=str(exc),
                )
            )
            continue
        results.append(result)

    _print_summary(results, command=command, dry_run=dry_run, out=out)

    if no_verify or dry_run:
        return 0

    rc = _verify(out=out, err=err)
    return rc


def _synthesize_host(kind: str, *, home: Path, cwd: Path) -> Optional[DetectedHost]:
    """Build a DetectedHost for a forced --host invocation."""
    if kind == "generic-mcp":
        return DetectedHost(kind=kind, config_path=None, note="forced")
    detected = {h.kind: h for h in detect_hosts(home=home, cwd=cwd)}
    if kind in detected:
        return detected[kind]
    # Synthesize the canonical config path even if the host isn't currently present.
    if kind == "claude-code-project":
        return DetectedHost(kind=kind, config_path=cwd / ".mcp.json", note="forced")
    if kind == "claude-code-user":
        return DetectedHost(
            kind=kind, config_path=home / ".claude" / "mcp.json", note="forced"
        )
    if kind == "cursor":
        return DetectedHost(
            kind=kind, config_path=home / ".cursor" / "mcp.json", note="forced"
        )
    if kind == "cline":
        system = platform.system()
        if system == "Darwin":
            base = _macos_app_support(home) / "Cline"
        elif system == "Windows":
            ad = _appdata_dir()
            base = (ad / "Cline") if ad else home / "Cline"
        else:
            base = _xdg_config_home(home) / "Cline"
        return DetectedHost(
            kind=kind, config_path=base / "cline_mcp_settings.json", note="forced"
        )
    if kind == "codex-cli":
        return DetectedHost(
            kind=kind, config_path=home / ".codex" / "config.toml", note="forced"
        )
    if kind == "codex-desktop":
        if platform.system() == "Darwin":
            p = _macos_app_support(home) / "Codex" / "config.json"
        elif platform.system() == "Windows":
            ad = _appdata_dir()
            p = (ad / "Codex" / "config.json") if ad else None
        else:
            p = None
        if p is None:
            return None
        return DetectedHost(kind=kind, config_path=p, note="forced")
    if kind == "claude-desktop":
        if platform.system() == "Darwin":
            p = _macos_app_support(home) / "Claude" / "claude_desktop_config.json"
        elif platform.system() == "Windows":
            ad = _appdata_dir()
            p = (ad / "Claude" / "claude_desktop_config.json") if ad else None
        else:
            p = None
        if p is None:
            return None
        return DetectedHost(kind=kind, config_path=p, note="forced")
    if kind in HOST_KINDS_DELEGATED:
        return DetectedHost(kind=kind, config_path=None, delegate_host=kind, note="forced")
    return None


def _print_summary(
    results: list[WriteResult], *, command: str, dry_run: bool, out: Any
) -> None:
    out.write("\nAINL setup\n")
    out.write(f"  command: {command}\n")
    if dry_run:
        out.write("  mode: --dry-run (no files written)\n")
    out.write("  hosts:\n")
    for r in results:
        path_repr = str(r.config_path) if r.config_path else "(delegated)"
        line = f"    - {r.kind:24s} {r.action:10s} {path_repr}"
        if r.detail:
            line += f" — {r.detail}"
        out.write(line + "\n")
        if r.backup_path:
            out.write(f"      backup: {r.backup_path}\n")


def _verify(*, out: Any, err: Any) -> int:
    """Run ``ainl doctor`` and surface its exit status."""
    import subprocess

    ainl_bin = shutil.which("ainl") or "ainl"
    try:
        proc = subprocess.run(
            [ainl_bin, "doctor"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        err.write(
            "\nverify: `ainl` not on PATH yet — install completed but `ainl doctor` "
            "could not run. Open a new shell and re-run `ainl doctor`.\n"
        )
        return 0
    if proc.returncode == 0:
        out.write("\nverify: ainl doctor → OK\n")
        return 0
    err.write(f"\nverify: ainl doctor → exit {proc.returncode}\n")
    if proc.stdout:
        err.write(proc.stdout)
    if proc.stderr:
        err.write(proc.stderr)
    err.write(
        "\n(this is non-fatal; some hosts require a restart before doctor sees the new server.)\n"
    )
    return 0  # non-fatal: setup itself succeeded


# ---------------------------------------------------------------------------
# argparse wiring helper (so cli/main.py stays terse)
# ---------------------------------------------------------------------------


def add_setup_subparser(sub: Any) -> None:
    """Wire ``ainl setup`` into the main argparse subparsers object."""
    p = sub.add_parser(
        "setup",
        help=(
            "One-step agent install: detect host(s) and register AINL's MCP server. "
            "Auto-detects Claude Code, Cursor, Cline, Codex CLI/Desktop, Claude Desktop, "
            "OpenClaw, Hermes, ArmaraOS."
        ),
    )
    p.add_argument(
        "--auto",
        action="store_true",
        default=True,
        help="(default) Configure every detected host. Idempotent.",
    )
    p.add_argument(
        "--host",
        choices=list(HOST_KINDS_DIRECT) + list(HOST_KINDS_DELEGATED) + ["generic-mcp"],
        default=None,
        help="Force a specific host instead of auto-detection.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan; write nothing.",
    )
    p.add_argument(
        "--print-config",
        action="store_true",
        help="Print the stdio JSON block for any generic MCP host and exit.",
    )
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the trailing `ainl doctor` step.",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=_setup_cmd_entry)


def _setup_cmd_entry(args: Any) -> int:
    delegate: Optional[Callable[[str, bool, bool], int]] = None
    try:
        from tooling.mcp_host_install import run_install_mcp_host

        def _delegate(host: str, dry_run: bool, verbose: bool) -> int:
            return run_install_mcp_host(host, dry_run=dry_run, verbose=verbose)

        delegate = _delegate
    except Exception:
        delegate = None
    return run_setup(
        target_host=getattr(args, "host", None),
        dry_run=bool(getattr(args, "dry_run", False)),
        no_verify=bool(getattr(args, "no_verify", False)),
        print_config_only=bool(getattr(args, "print_config", False)),
        verbose=bool(getattr(args, "verbose", False)),
        delegate=delegate,
    )
