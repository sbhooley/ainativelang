#!/usr/bin/env python3
"""Git-style entrypoint for ArmaraOS bridge tools (delegates to scripts in this directory)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent

_SKIP_DISCOVER = frozenset(
    {
        "_shim_delegate.py",
        "ainl_bridge_main.py",
        "generate_shims.py",
        "__init__.py",
    }
)

# Served by fixed aliases — do not register again from filename
_EXPLICIT_SCRIPT_STEMS = frozenset(
    {
        "run_wrapper_ainl",
        "cron_drift_check",
        "ainl_memory_append_cli",
    }
)

_EXPLICIT: dict[str, str] = {
    "run-wrapper": "run_wrapper_ainl.py",
    "drift-check": "cron_drift_check.py",
    "memory-append": "ainl_memory_append_cli.py",
}

# Run ainl_armaraos_validate() only for these bridge commands (not for every tool).
_VALIDATE_CMDS = frozenset({"run-wrapper", "token-usage", "drift-check", "memory-append"})

_GOLD_STANDARD_CRON_NAMES = frozenset(
    {
        "AINL Context Injection",
        "AINL Session Summarizer",
        "AINL Weekly Token Trends",
    }
)


def ainl_armaraos_validate() -> dict:
    """Lightweight ArmaraOS integration validator (best-effort; auto-creates SQLite tables)."""
    import json
    import subprocess
    import time
    from pathlib import Path
    from armaraos.bridge.schema_bootstrap import bootstrap_tables
    from armaraos.bridge.user_friendly_error import INIT_INSTALL_ARMARAOS
    from armaraos.env import resolve_armaraos_env

    t0 = time.time()
    warnings: list[str] = []
    env = resolve_armaraos_env()

    missing: list[str] = []
    if not env.workspace:
        missing.append("ARMARAOS_WORKSPACE")
    if not env.memory_dir:
        missing.append("ARMARAOS_MEMORY_DIR")
    if not env.fs_root:
        missing.append("AINL_FS_ROOT")
    if not env.memory_db:
        missing.append("AINL_MEMORY_DB")
    if not env.monitor_cache_json:
        missing.append("MONITOR_CACHE_JSON")
    if not env.ir_cache_dir:
        missing.append("AINL_IR_CACHE_DIR")

    if not env.prefer_session_context:
        warnings.append("ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT is not true — " + INIT_INSTALL_ARMARAOS)

    db_path = Path(env.memory_db).expanduser()
    schema_ok, schema_detail = bootstrap_tables(db_path)

    cron_ok: bool | None = None
    cron_detail = "skipped"
    try:
        proc = subprocess.run(["armaraos", "cron", "list", "--json"], capture_output=True, text=True, timeout=2.0)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            jobs = data.get("jobs") if isinstance(data, dict) else None
            names = {str(j.get("name")) for j in jobs if isinstance(j, dict)} if isinstance(jobs, list) else set()
            missing_jobs = sorted(_GOLD_STANDARD_CRON_NAMES - names)
            cron_ok = len(missing_jobs) == 0
            cron_detail = "ok" if cron_ok else ("missing: " + ", ".join(missing_jobs))
        else:
            cron_ok = None
            cron_detail = (proc.stderr or proc.stdout or "").strip()[:200]
            warnings.append("could not list ArmaraOS crons: " + cron_detail)
    except FileNotFoundError:
        cron_ok = None
        cron_detail = "armaraos CLI not found"
        warnings.append("armaraos CLI not on PATH — cron check skipped")
    except Exception as e:
        cron_ok = None
        cron_detail = str(e)[:200]
        warnings.append("cron check failed: " + cron_detail)

    ok = (not missing) and schema_ok  # crons/prefer are warnings only
    return {
        "ok": ok,
        "missing_env": missing,
        "schema_ok": schema_ok,
        "schema_detail": schema_detail,
        "cron_ok": cron_ok,
        "cron_detail": cron_detail,
        "warnings": warnings,
        "duration_ms": (time.time() - t0) * 1000,
    }


def main() -> None:
    """Dispatch to a Python script in the bridge directory.

    Usage: python -m armaraos.bridge.ainl_bridge_main <script_name> [args...]
    Example: python -m armaraos.bridge.ainl_bridge_main run-wrapper --ainl foo.ainl
    """
    if len(sys.argv) < 2:
        print("Usage: python -m armaraos.bridge.ainl_bridge_main <script_name> [args...]", file=sys.stderr)
        sys.exit(2)

    script_name = sys.argv[1]
    if script_name in _EXPLICIT:
        script_file = _EXPLICIT[script_name]
    elif script_name in _EXPLICIT_SCRIPT_STEMS:
        script_file = f"{script_name}.py"
    else:
        # Auto-discover .py files in this directory
        this_dir = _BRIDGE
        candidates = [
            p for p in this_dir.iterdir()
            if p.suffix == ".py" and p.name not in _SKIP_DISCOVER and p.name not in {f"{s}.py" for s in _EXPLICIT_SCRIPT_STEMS}
        ]
        match = [p for p in candidates if p.stem == script_name]
        if not match:
            print(f"Error: unknown bridge script '{script_name}'. Available: {', '.join(sorted([p.stem for p in candidates] + list(_EXPLICIT.keys())))}", file=sys.stderr)
            sys.exit(2)
        script_file = match[0].name

    # Re-execute the script as __main__ with same argv
    sys.argv = [str(_BRIDGE / script_file)] + sys.argv[2:]
    runpy.run_path(str(_BRIDGE / script_file), run_name="__main__")


if __name__ == "__main__":
    main()
