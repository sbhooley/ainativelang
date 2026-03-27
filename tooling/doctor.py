from __future__ import annotations

import json
import os
import re
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

    if profile.config_kind == "yaml_mcp_servers":
        # Keep this intentionally minimal — installer uses a text merge too.
        text = ""
        try:
            text = cfg.read_text(encoding="utf-8")
        except Exception:
            text = ""
        if "mcp_servers:" not in text:
            return _warn(f"mcp_config_{host_id}", f"{cfg} missing top-level mcp_servers: block")
        needle = f"\n  {MCP_SERVER_KEY}:"
        if needle not in text and not text.lstrip().startswith(f"mcp_servers:\n  {MCP_SERVER_KEY}:"):
            return _warn(f"mcp_config_{host_id}", f"{cfg} missing mcp_servers.{MCP_SERVER_KEY}")
        m = re.search(rf"^\s*command:\s*\"?([^\n\"]+)\"?\s*$", text, flags=re.MULTILINE)
        cmd = (m.group(1).strip() if m else "")
        hermes_hint = ""
        if host_id == "hermes":
            hermes_hint = (
                " MCP server `ainl` is registered for stdio; after adding skill bundles under "
                "`~/.hermes/skills/ainl-imports/`, refresh Hermes’ skills index (e.g. restart the agent or use your "
                "CLI’s skills reload if available)."
            )
        if not cmd:
            return _ok(
                f"mcp_config_{host_id}",
                f"{cfg} has mcp_servers.{MCP_SERVER_KEY} (command not parsed){hermes_hint}",
            )
        return _ok(
            f"mcp_config_{host_id}",
            f"{cfg} has mcp_servers.{MCP_SERVER_KEY} registered command={cmd}.{hermes_hint}",
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


def run_doctor(*, host: Optional[str] = None, json_output: bool = False, verbose: bool = False, ainl_openclaw: bool = False) -> int:  # AINL-OPENCLAW-TOP5
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

    if ainl_openclaw:  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            from openclaw.bridge.ainl_bridge_main import ainl_openclaw_validate  # AINL-OPENCLAW-TOP5
            from openclaw.bridge.user_friendly_error import user_friendly_ainl_error  # AINL-OPENCLAW-TOP5

            rep = ainl_openclaw_validate()  # AINL-OPENCLAW-TOP5
            for i, w in enumerate(rep.get("warnings") or []):  # AINL-OPENCLAW-TOP5
                checks.append(_warn(f"openclaw_ainl_warning_{i}", user_friendly_ainl_error(RuntimeError(str(w)))))  # AINL-OPENCLAW-TOP5
            missing = rep.get("missing_env") or []  # AINL-OPENCLAW-TOP5
            _ws_path = str(Path.home() / ".openclaw" / "workspace")  # AINL-OPENCLAW-TOP5
            fix_ws = f" (fix: `ainl install openclaw --workspace {_ws_path}`)"  # AINL-OPENCLAW-TOP5
            if missing:  # AINL-OPENCLAW-TOP5
                checks.append(  # AINL-OPENCLAW-TOP5
                    _warn(  # AINL-OPENCLAW-TOP5
                        "openclaw_ainl_env",  # AINL-OPENCLAW-TOP5
                        "missing env var(s): " + ", ".join(str(x) for x in missing) + fix_ws,  # AINL-OPENCLAW-TOP5
                    )  # AINL-OPENCLAW-TOP5
                )  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                checks.append(_ok("openclaw_ainl_env", "required env vars present"))  # AINL-OPENCLAW-TOP5
            if rep.get("schema_ok"):  # AINL-OPENCLAW-TOP5
                checks.append(_ok("openclaw_ainl_schema", str(rep.get("schema_detail") or "ok")))  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                checks.append(_warn("openclaw_ainl_schema", str(rep.get("schema_detail") or "schema missing") + fix_ws))  # AINL-OPENCLAW-TOP5
            if rep.get("cron_ok") is True:  # AINL-OPENCLAW-TOP5
                checks.append(_ok("openclaw_ainl_cron", "gold-standard cron jobs (3) present"))  # AINL-OPENCLAW-TOP5
            elif rep.get("cron_ok") is False:  # AINL-OPENCLAW-TOP5
                checks.append(_warn("openclaw_ainl_cron", str(rep.get("cron_detail") or "core jobs missing") + fix_ws))  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                checks.append(_warn("openclaw_ainl_cron", str(rep.get("cron_detail") or "cron check unavailable")))  # AINL-OPENCLAW-TOP5
            if rep.get("prefer_session_context") is True:  # AINL-OPENCLAW-TOP5
                checks.append(_ok("openclaw_bootstrap_prefer_session_context", "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=true"))  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                checks.append(_warn("openclaw_bootstrap_prefer_session_context", "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT is false" + fix_ws))  # AINL-OPENCLAW-TOP5
        except Exception as exc:  # AINL-OPENCLAW-TOP5
            checks.append(_warn("openclaw_ainl_validate", f"validator failed: {exc}"))  # AINL-OPENCLAW-TOP5

    payload: Dict[str, Any] = {  # AINL-OPENCLAW-TOP5
        "ok": all(c.status != "fail" for c in checks),  # AINL-OPENCLAW-TOP5
        "checks": [asdict(c) for c in checks],  # AINL-OPENCLAW-TOP5
    }  # AINL-OPENCLAW-TOP5
    if ainl_openclaw:  # AINL-OPENCLAW-TOP5
        _ws_suggest = str(Path.home() / ".openclaw" / "workspace")  # AINL-OPENCLAW-TOP5
        payload["openclaw_ainl_fix_suggestions"] = [  # AINL-OPENCLAW-TOP5
            f"ainl install openclaw --workspace {_ws_suggest}",  # AINL-OPENCLAW-TOP5
            "ainl status --json",  # AINL-OPENCLAW-TOP5
            "ainl doctor --ainl",  # AINL-OPENCLAW-TOP5
        ]  # AINL-OPENCLAW-TOP5

    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        for c in checks:
            prefix = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[c.status]
            print(f"[{prefix}] {c.name}: {c.detail}")
        print(f"\nAINL doctor overall: {'PASS' if payload['ok'] else 'FAIL'}")
        if ainl_openclaw:  # AINL-OPENCLAW-TOP5
            print("\nOpenClaw + AINL — copy/paste fixes (if any checks warned):")  # AINL-OPENCLAW-TOP5
            for s in payload.get("openclaw_ainl_fix_suggestions") or []:  # AINL-OPENCLAW-TOP5
                print(f"  • {s}")  # AINL-OPENCLAW-TOP5
        if verbose:
            print(f"Checked hosts: {', '.join(hosts)}")

    return 0 if payload["ok"] else 1
