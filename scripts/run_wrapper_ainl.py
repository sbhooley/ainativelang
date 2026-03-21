#!/usr/bin/env python3
"""Run orchestration wrappers under the OpenClaw monitor registry plus new bridge adapters.

Usage:
  python3 scripts/run_wrapper_ainl.py <github-intelligence|content-engine|supervisor> [--dry-run] [--trace]

Dry-run: sets frame[\"dry_run\"] so adapters skip network/disk side effects; execution still proceeds.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine

from adapters.crm import CrmAdapter
from adapters.github import GitHubAdapter
from adapters.openclaw_defaults import DEFAULT_CRM_HEALTH_URL
from adapters.openclaw_integration import openclaw_monitor_registry
from adapters.openclaw_memory import OpenClawMemoryAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ainl.wrapper")

WRAPPERS = {
    "github-intelligence": ROOT / "scripts" / "wrappers" / "github-intelligence.ainl",
    "content-engine": ROOT / "scripts" / "wrappers" / "content-engine.ainl",
    "supervisor": ROOT / "scripts" / "wrappers" / "supervisor.ainl",
}


def _crm_health_url() -> str:
    """Health probe URL for content-engine. Prefer CRM_HEALTH_URL, else CRM_API_BASE + /api/health."""
    explicit = os.environ.get("CRM_HEALTH_URL")
    if explicit:
        return explicit.strip()
    if os.environ.get("CRM_API_BASE"):
        return f'{os.environ["CRM_API_BASE"].rstrip("/")}/api/health'
    return DEFAULT_CRM_HEALTH_URL


def build_wrapper_registry():
    # WebAdapter() in openclaw_monitor_registry() requires a non-empty key at import/init time.
    if not (os.environ.get("OPENROUTER_API_KEY") or "").strip():
        os.environ["OPENROUTER_API_KEY"] = os.environ.get(
            "AINL_OPENROUTER_PLACEHOLDER_KEY", "unset-openrouter-key-wrapper-registry"
        )
    reg = openclaw_monitor_registry()
    for name in ("openclaw_memory", "github", "crm"):
        reg.allow(name)
    reg.register("openclaw_memory", OpenClawMemoryAdapter())
    reg.register("github", GitHubAdapter())
    reg.register("crm", CrmAdapter())
    return reg


def main() -> None:
    argv = [a for a in sys.argv[1:] if a]
    trace = "--trace" in argv
    dry = "--dry-run" in argv
    argv = [a for a in argv if a not in ("--trace", "--dry-run")]
    if not argv:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    name = argv[0]
    path = WRAPPERS.get(name)
    if not path or not path.is_file():
        logger.error("Unknown wrapper %r; known: %s", name, ", ".join(WRAPPERS))
        sys.exit(1)

    src = path.read_text(encoding="utf-8")
    ir = AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src, emit_graph=True)
    errs = ir.get("errors") or []
    if errs:
        logger.error("Compile errors: %s", errs)
        sys.exit(2)

    reg = build_wrapper_registry()
    eng = RuntimeEngine(ir, adapters=reg, trace=trace, execution_mode="graph-preferred")
    frame: dict = {
        # content-engine.ainl: R extras http_status crm_health_url
        "crm_health_url": _crm_health_url(),
    }
    if dry:
        frame["dry_run"] = True
        os.environ.setdefault("AINL_DRY_RUN", "1")

    try:
        out = eng.run_label("0", frame)
    except Exception as e:
        logger.exception("Runtime error: %s", e)
        sys.exit(3)

    payload = {"ok": True, "wrapper": name, "out": out}
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
