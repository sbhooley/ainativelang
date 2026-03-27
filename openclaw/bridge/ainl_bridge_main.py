#!/usr/bin/env python3
"""Git-style entrypoint for OpenClaw bridge tools (delegates to scripts in this directory)."""
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

# Run ainl_openclaw_validate() only for these bridge commands (not for every tool).  # AINL-OPENCLAW-TOP5
_VALIDATE_CMDS = frozenset({"run-wrapper", "token-usage", "drift-check", "memory-append"})  # AINL-OPENCLAW-TOP5

_GOLD_STANDARD_CRON_NAMES = frozenset(  # AINL-OPENCLAW-TOP5
    {  # AINL-OPENCLAW-TOP5
        "AINL Context Injection",  # AINL-OPENCLAW-TOP5
        "AINL Session Summarizer",  # AINL-OPENCLAW-TOP5
        "AINL Weekly Token Trends",  # AINL-OPENCLAW-TOP5
    }  # AINL-OPENCLAW-TOP5
)  # AINL-OPENCLAW-TOP5


def ainl_openclaw_validate() -> dict:  # AINL-OPENCLAW-TOP5
    """Lightweight OpenClaw integration validator (best-effort; auto-creates SQLite tables)."""  # AINL-OPENCLAW-TOP5
    import json  # AINL-OPENCLAW-TOP5
    import os  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    import time  # AINL-OPENCLAW-TOP5
    from pathlib import Path  # AINL-OPENCLAW-TOP5
    from openclaw.bridge.schema_bootstrap import bootstrap_tables  # AINL-OPENCLAW-TOP5
    from openclaw.bridge.user_friendly_error import INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5

    t0 = time.time()  # AINL-OPENCLAW-TOP5
    warnings: list[str] = []  # AINL-OPENCLAW-TOP5
    required_env = [  # AINL-OPENCLAW-TOP5
        "OPENCLAW_WORKSPACE",  # AINL-OPENCLAW-TOP5
        "OPENCLAW_MEMORY_DIR",  # AINL-OPENCLAW-TOP5
        "AINL_FS_ROOT",  # AINL-OPENCLAW-TOP5
        "AINL_MEMORY_DB",  # AINL-OPENCLAW-TOP5
        "MONITOR_CACHE_JSON",  # AINL-OPENCLAW-TOP5
        "AINL_IR_CACHE_DIR",  # AINL-OPENCLAW-TOP5
    ]  # AINL-OPENCLAW-TOP5
    missing = [k for k in required_env if not str(os.getenv(k, "")).strip()]  # AINL-OPENCLAW-TOP5
    prefer = str(os.getenv("OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT", "")).strip().lower()  # AINL-OPENCLAW-TOP5
    prefer_ok = prefer in ("1", "true", "yes", "on")  # AINL-OPENCLAW-TOP5
    if not prefer_ok:  # AINL-OPENCLAW-TOP5
        warnings.append("OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT is not true — " + INIT_INSTALL_OPENCLAW)  # AINL-OPENCLAW-TOP5

    db_path = Path(os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")).expanduser()  # AINL-OPENCLAW-TOP5
    schema_ok, schema_detail = bootstrap_tables(db_path)  # AINL-OPENCLAW-TOP5

    cron_ok: bool | None = None  # AINL-OPENCLAW-TOP5
    cron_detail = "skipped"  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        proc = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=2.0)  # AINL-OPENCLAW-TOP5
        if proc.returncode == 0:  # AINL-OPENCLAW-TOP5
            data = json.loads(proc.stdout)  # AINL-OPENCLAW-TOP5
            jobs = data.get("jobs") if isinstance(data, dict) else None  # AINL-OPENCLAW-TOP5
            names = {str(j.get("name")) for j in jobs if isinstance(j, dict)} if isinstance(jobs, list) else set()  # AINL-OPENCLAW-TOP5
            missing_jobs = sorted(_GOLD_STANDARD_CRON_NAMES - names)  # AINL-OPENCLAW-TOP5
            cron_ok = len(missing_jobs) == 0  # AINL-OPENCLAW-TOP5
            cron_detail = "ok" if cron_ok else ("missing: " + ", ".join(missing_jobs))  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            cron_ok = None  # AINL-OPENCLAW-TOP5
            cron_detail = (proc.stderr or proc.stdout or "").strip()[:200]  # AINL-OPENCLAW-TOP5
            warnings.append("could not list OpenClaw crons: " + cron_detail)  # AINL-OPENCLAW-TOP5
    except FileNotFoundError:  # AINL-OPENCLAW-TOP5
        cron_ok = None  # AINL-OPENCLAW-TOP5
        cron_detail = "openclaw CLI not found"  # AINL-OPENCLAW-TOP5
        warnings.append("openclaw CLI not on PATH — cron check skipped")  # AINL-OPENCLAW-TOP5
    except Exception as e:  # AINL-OPENCLAW-TOP5
        cron_ok = None  # AINL-OPENCLAW-TOP5
        cron_detail = str(e)[:200]  # AINL-OPENCLAW-TOP5
        warnings.append("cron check failed: " + cron_detail)  # AINL-OPENCLAW-TOP5

    ok = (not missing) and schema_ok  # AINL-OPENCLAW-TOP5 — crons/prefer are warnings only  # AINL-OPENCLAW-TOP5
    return {  # AINL-OPENCLAW-TOP5
        "ok": ok,  # AINL-OPENCLAW-TOP5
        "missing_env": missing,  # AINL-OPENCLAW-TOP5
        "schema_ok": schema_ok,  # AINL-OPENCLAW-TOP5
        "schema_detail": schema_detail,  # AINL-OPENCLAW-TOP5
        "cron_ok": cron_ok,  # AINL-OPENCLAW-TOP5
        "cron_detail": cron_detail,  # AINL-OPENCLAW-TOP5
        "prefer_session_context": prefer_ok,  # AINL-OPENCLAW-TOP5
        "warnings": warnings,  # AINL-OPENCLAW-TOP5
        "elapsed_ms": int(round((time.time() - t0) * 1000.0)),  # AINL-OPENCLAW-TOP5
    }  # AINL-OPENCLAW-TOP5


def _discovered() -> dict[str, str]:
    """CLI name (hyphenated) -> bridge script basename."""
    out: dict[str, str] = {}
    for p in sorted(_BRIDGE.glob("*.py")):
        if p.name in _SKIP_DISCOVER:
            continue
        if p.stem.startswith("test_"):
            continue
        if p.stem in _EXPLICIT_SCRIPT_STEMS:
            continue
        rel = p.relative_to(_BRIDGE)
        if "tests" in rel.parts:
            continue
        cli = p.stem.replace("_", "-")
        if cli in _EXPLICIT or cli in out:
            continue
        out[cli] = p.name
    if out.get("token-usage-reporter") == "token_usage_reporter.py":
        out["token-usage"] = out.pop("token-usage-reporter")
    return out


def _all_commands() -> dict[str, str]:
    m = dict(_discovered())
    m.update(_EXPLICIT)
    return m


def _print_help() -> None:
    auto = _discovered()
    names = sorted(_all_commands().keys())
    print(
        "usage: python3 openclaw/bridge/ainl_bridge_main.py <command> [args...]\n\n"
        "OpenClaw bridge entrypoint: runs tools in openclaw/bridge/. "
        "Fixed aliases (run-wrapper, drift-check, memory-append) plus auto-discovered bridge tools.\n"
    )
    print("commands:\n  " + "\n  ".join(names))
    print(
        "\nAuto-discovered tools (subset): "
        + (", ".join(sorted(auto)) if auto else "(none)")
        + "\n\nArguments after <command> are forwarded verbatim (--dry-run, --json, etc.)."
    )


def _run_script(filename: str, forward: list[str]) -> None:
    sys.argv = [filename] + forward
    runpy.run_path(str(_BRIDGE / filename), run_name="__main__")


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        _print_help()
        sys.exit(0)
    cmd, *rest = argv
    # Validator on bridge-heavy commands only (warn; never exit).  # AINL-OPENCLAW-TOP5
    if cmd in _VALIDATE_CMDS:  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            from openclaw.bridge.user_friendly_error import user_friendly_ainl_error  # AINL-OPENCLAW-TOP5

            report = ainl_openclaw_validate()  # AINL-OPENCLAW-TOP5
            for w in report.get("warnings") or []:  # AINL-OPENCLAW-TOP5
                print("Warning: " + user_friendly_ainl_error(RuntimeError(w)), file=sys.stderr)  # AINL-OPENCLAW-TOP5
        except Exception as exc:  # AINL-OPENCLAW-TOP5
            try:  # AINL-OPENCLAW-TOP5
                from openclaw.bridge.user_friendly_error import user_friendly_ainl_error  # AINL-OPENCLAW-TOP5

                print("Warning: " + user_friendly_ainl_error(exc), file=sys.stderr)  # AINL-OPENCLAW-TOP5
            except Exception:  # AINL-OPENCLAW-TOP5
                print("Warning: ainl_openclaw_validate failed: " + str(exc), file=sys.stderr)  # AINL-OPENCLAW-TOP5
    cmap = _all_commands()
    if cmd not in cmap:
        print(f"ainl_bridge_main.py: unknown command {cmd!r} (try --help)", file=sys.stderr)
        sys.exit(2)
    _run_script(cmap[cmd], rest)


if __name__ == "__main__":
    main()
