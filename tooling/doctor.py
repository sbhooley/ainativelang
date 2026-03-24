from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tooling.mcp_host_install import MCP_SERVER_KEY, PROFILES


@dataclass
class DoctorCheck:
    name: str
    status: str
    detail: str


def _ok(name: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status="ok", detail=detail)


def _warn(name: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status="warn", detail=detail)


def _fail(name: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status="fail", detail=detail)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _check_host_config(home: Path, host_id: str) -> DoctorCheck:
    profile = PROFILES[host_id]
    cfg = home / profile.dot_rel / profile.config_filename
    if not cfg.exists():
        return _warn(
            f"mcp_config_{host_id}",
            f"{cfg} not found (run: ainl install-mcp --host {host_id})",
        )
    data = _read_json(cfg)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return _warn(f"mcp_config_{host_id}", f"{cfg} has no object mcpServers key")
    server = servers.get(MCP_SERVER_KEY)
    if not isinstance(server, dict):
        return _warn(f"mcp_config_{host_id}", f"{cfg} missing mcpServers.{MCP_SERVER_KEY}")
    cmd = str(server.get("command") or "").strip()
    if not cmd:
        return _warn(f"mcp_config_{host_id}", f"{cfg} has empty mcpServers.{MCP_SERVER_KEY}.command")
    return _ok(f"mcp_config_{host_id}", f"{cfg} has mcpServers.{MCP_SERVER_KEY} command={cmd}")


def _check_help_invocation(name: str, exe: Optional[str], timeout_s: float = 8.0) -> DoctorCheck:
    if not exe:
        return _warn(f"help_{name}", f"{name} not on PATH")
    try:
        proc = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return _warn(f"help_{name}", f"{name} --help timed out after {timeout_s:.0f}s")
    except Exception as exc:
        return _warn(f"help_{name}", f"{name} --help failed: {exc}")
    if proc.returncode == 0:
        return _ok(f"help_{name}", f"{name} --help succeeded")
    msg = (proc.stderr or proc.stdout).strip()
    return _warn(f"help_{name}", f"{name} --help exit={proc.returncode}: {msg[:220]}")


def run_doctor(*, host: Optional[str] = None, json_output: bool = False, verbose: bool = False) -> int:
    checks: List[DoctorCheck] = []
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        checks.append(_ok("python_version", f"python={py_ver} (>=3.10)"))
    else:
        checks.append(_fail("python_version", f"python={py_ver} (<3.10 unsupported)"))

    for mod in ("runtime.compat", "adapters", "cli.main"):
        try:
            __import__(mod)
            checks.append(_ok(f"import_{mod}", "import succeeded"))
        except Exception as exc:  # pragma: no cover
            checks.append(_fail(f"import_{mod}", f"import failed: {exc}"))

    ainl_path = shutil.which("ainl")
    ainl_mcp_path = shutil.which("ainl-mcp")
    checks.append(_ok("path_ainl", f"found at {ainl_path}") if ainl_path else _warn("path_ainl", "ainl not on PATH"))
    checks.append(
        _ok("path_ainl_mcp", f"found at {ainl_mcp_path}") if ainl_mcp_path else _warn("path_ainl_mcp", "ainl-mcp not on PATH")
    )
    checks.append(_check_help_invocation("ainl", ainl_path))
    checks.append(_check_help_invocation("ainl-mcp", ainl_mcp_path))

    user_base = Path(sys.prefix if hasattr(sys, "prefix") else Path.home())
    try:
        user_base = Path(
            subprocess.check_output([sys.executable, "-m", "site", "--user-base"], text=True).strip() or str(user_base)
        )
    except Exception:
        pass
    user_bin = user_base / "bin"
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if str(user_bin) in path_parts:
        checks.append(_ok("path_user_bin", f"{user_bin} in PATH"))
    else:
        checks.append(_warn("path_user_bin", f"{user_bin} not in PATH"))

    hosts = [host] if host else sorted(PROFILES.keys())
    for hid in hosts:
        if hid not in PROFILES:
            checks.append(_fail("doctor_host", f"unknown host {hid!r}; expected one of: {', '.join(sorted(PROFILES))}"))
            continue
        checks.append(_check_host_config(Path.home(), hid))

    for hid in hosts:
        if hid not in PROFILES or not ainl_path:
            continue
        cmd = [ainl_path, "install-mcp", "--host", hid, "--dry-run"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            checks.append(_ok(f"install_mcp_dry_run_{hid}", "dry-run succeeded"))
        else:
            msg = (proc.stderr or proc.stdout).strip()
            checks.append(_warn(f"install_mcp_dry_run_{hid}", f"dry-run failed (exit={proc.returncode}): {msg[:240]}"))

    payload = {
        "ok": all(c.status != "fail" for c in checks),
        "checks": [asdict(c) for c in checks],
    }

    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        for c in checks:
            prefix = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[c.status]
            print(f"[{prefix}] {c.name}: {c.detail}")
        print(f"\nAINL doctor overall: {'PASS' if payload['ok'] else 'FAIL'}")
        if verbose:
            print(f"Checked hosts: {', '.join(hosts)}")

    return 0 if payload["ok"] else 1
