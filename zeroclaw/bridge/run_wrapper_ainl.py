#!/usr/bin/env python3
"""Run orchestration wrappers with ZeroClaw-local memory, queue, and token bridge.

Official location: ``zeroclaw/bridge/`` (ZeroClaw integration layer; not AINL core).

Execution model
---------------
By default this embeds ``RuntimeEngine`` (same pattern as ``openclaw/bridge/run_wrapper_ainl.py``)
with a registry tuned for ``~/.zeroclaw/``. Bare ``ainl run`` does **not** load this registry, so
bridge wrappers should be launched via this script or ``zeroclaw-ainl-run``.

Optional: set ``AINL_ZC_COMPILE_SUBPROCESS=1`` to run ``ainl compile <wrapper>`` in a subprocess
before executing (validates toolchain); graph execution stays in-process.

Usage:
  python3 zeroclaw/bridge/run_wrapper_ainl.py <name> [--dry-run] [--trace] [--verbose] [--json] [--output {text,json}] [--pretty]

Dry-run: sets frame[\"dry_run\"] and ``AINL_DRY_RUN`` so adapters skip network/disk side effects.

JSON stdout: ``--dry-run`` always prints ``{"status": "ok", "out": ..., "wrapper": ...}``.
On live runs, stdout is silent unless ``--json`` or ``--output=json`` (same envelope).

- ``--json``: emit JSON on live runs (useful for scripting).
- ``--pretty``: indent JSON output (dry-run, ``--json``, or ``--output=json``).

Examples:

  zeroclaw-ainl-run weekly-token-trends --json --pretty
  zeroclaw-ainl-run monthly-token-summary --output=json --pretty

With ``AINL_ZC_COMPILE_SUBPROCESS=1``, ``--verbose`` logs the ``ainl compile`` subprocess
command, exit code, and stderr (truncated).

``--verbose`` / ``-v`` also sets ``AINL_ZC_WRAPPER_VERBOSE=1`` so the bridge logs extra runtime
detail (e.g. which daily ``*.md`` files ``weekly_token_trends`` / ``monthly_token_summary`` considered).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

_BRIDGE_DIR = Path(__file__).resolve().parent
ROOT = _BRIDGE_DIR.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine

from adapters.crm import CrmAdapter
from adapters.github import GitHubAdapter
from adapters.openclaw_defaults import DEFAULT_CRM_HEALTH_URL
from adapters.openclaw_integration import openclaw_monitor_registry

import importlib.util


def _load_bridge_module(stem: str):
    spec = importlib.util.spec_from_file_location(stem, _BRIDGE_DIR / f"{stem}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_zmem = _load_bridge_module("zeroclaw_memory_adapter")
ZeroclawMemoryAdapter = _zmem.ZeroclawMemoryAdapter

_tok = _load_bridge_module("token_budget_adapter")
ZeroclawBridgeTokenBudgetAdapter = _tok.ZeroclawBridgeTokenBudgetAdapter

_q = _load_bridge_module("zeroclaw_queue_adapter")
ZeroclawQueueAdapter = _q.ZeroclawQueueAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ainl.zeroclaw.wrapper")

WRAPPERS = {
    "github-intelligence": ROOT / "scripts" / "wrappers" / "github-intelligence.ainl",
    "content-engine": ROOT / "scripts" / "wrappers" / "content-engine.ainl",
    "supervisor": ROOT / "scripts" / "wrappers" / "supervisor.ainl",
    "full-unification": ROOT / "examples" / "openclaw_full_unification.ainl",
    "token-budget-alert": _BRIDGE_DIR / "wrappers" / "token_budget_alert.ainl",
    "weekly-token-trends": _BRIDGE_DIR / "wrappers" / "weekly_token_trends.ainl",
    "monthly-token-summary": _BRIDGE_DIR / "wrappers" / "monthly_token_summary.ainl",
}


def _crm_health_url() -> str:
    explicit = os.environ.get("CRM_HEALTH_URL")
    if explicit:
        return explicit.strip()
    if os.environ.get("CRM_API_BASE"):
        return f'{os.environ["CRM_API_BASE"].rstrip("/")}/api/health'
    return DEFAULT_CRM_HEALTH_URL


def _zeroclaw_workspace_root() -> str:
    return os.getenv("ZEROCLAW_WORKSPACE", str(Path.home() / ".zeroclaw" / "workspace"))


def build_wrapper_registry():
    if not (os.environ.get("OPENROUTER_API_KEY") or "").strip():
        os.environ["OPENROUTER_API_KEY"] = os.environ.get(
            "AINL_OPENROUTER_PLACEHOLDER_KEY", "unset-openrouter-key-wrapper-registry"
        )
    reg = openclaw_monitor_registry()
    zmem = ZeroclawMemoryAdapter()
    for name in ("openclaw_memory", "zeroclaw_memory", "github", "crm"):
        reg.allow(name)
    # Shared wrappers use R openclaw_memory; under ZeroClaw bridge, route to ~/.zeroclaw workspace files.
    reg.register("openclaw_memory", zmem)
    reg.register("zeroclaw_memory", zmem)
    reg.register("github", GitHubAdapter())
    reg.register("crm", CrmAdapter())
    reg.allow("bridge")
    reg.register("bridge", ZeroclawBridgeTokenBudgetAdapter())
    reg.register("queue", ZeroclawQueueAdapter())

    from runtime.adapters.fs import SandboxedFileSystemAdapter

    reg.register(
        "fs",
        SandboxedFileSystemAdapter(
            sandbox_root=_zeroclaw_workspace_root(),
            max_read_bytes=2_000_000,
            max_write_bytes=2_000_000,
            allow_delete=False,
        ),
    )
    return reg


def _maybe_subprocess_compile(path: Path, *, verbose: bool) -> None:
    if os.environ.get("AINL_ZC_COMPILE_SUBPROCESS", "").strip().lower() not in ("1", "true", "yes"):
        return
    ainl = shutil.which("ainl")
    if not ainl:
        logger.warning("AINL_ZC_COMPILE_SUBPROCESS set but ainl not on PATH; skipping")
        return
    cmd = [ainl, "compile", str(path)]
    if verbose:
        logger.info("AINL_ZC_COMPILE_SUBPROCESS: cwd=%s cmd=%s", ROOT, cmd)
    r = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if verbose:
        logger.info("ainl compile subprocess exit=%s", r.returncode)
        err = (r.stderr or "").strip()
        out = (r.stdout or "").strip()
        if err:
            logger.info("ainl compile stderr (truncated): %s", err[:800])
        if out:
            logger.info("ainl compile stdout (truncated): %s", out[:800])
    if r.returncode != 0:
        logger.warning("subprocess ainl compile failed: %s", (r.stderr or r.stdout)[:400])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run ZeroClaw bridge wrappers (memory, queue, token budget).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Wrapper CLI name (e.g. weekly-token-trends)")
    parser.add_argument("--dry-run", action="store_true", help="Skip append_today, queue notify, etc.")
    parser.add_argument("--trace", action="store_true", help="Trace graph execution")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose bridge logs (AINL_ZC_WRAPPER_VERBOSE)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="On live runs, print JSON envelope to stdout (dry-run always prints JSON)",
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="text: default live stdout silence; json: same as --json on live runs (POSIX-style alias)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON when emitting (dry-run, --json, or --output=json)",
    )
    args = parser.parse_args()

    if args.verbose:
        os.environ["AINL_ZC_WRAPPER_VERBOSE"] = "1"
    name = args.name
    path = WRAPPERS.get(name)
    if not path or not path.is_file():
        logger.error("Unknown wrapper %r; known: %s", name, ", ".join(WRAPPERS))
        sys.exit(1)

    _maybe_subprocess_compile(path, verbose=args.verbose)

    src = path.read_text(encoding="utf-8")
    ir = AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src, emit_graph=True)
    errs = ir.get("errors") or []
    if errs:
        logger.error("Compile errors: %s", errs)
        sys.exit(2)

    reg = build_wrapper_registry()
    eng = RuntimeEngine(ir, adapters=reg, trace=args.trace, execution_mode="graph-preferred")
    frame: dict = {
        "crm_health_url": _crm_health_url(),
    }
    if args.dry_run:
        frame["dry_run"] = True
        os.environ.setdefault("AINL_DRY_RUN", "1")

    try:
        out = eng.run_label("0", frame)
    except Exception as e:
        logger.exception("Runtime error: %s", e)
        sys.exit(3)

    emit_json = args.dry_run or args.json or args.output == "json"
    if emit_json:
        md = "" if out is None else out
        data = {"status": "ok", "out": md, "wrapper": name}
        if args.pretty:
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        else:
            print(json.dumps(data, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
