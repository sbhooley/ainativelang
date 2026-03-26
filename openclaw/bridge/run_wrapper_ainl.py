#!/usr/bin/env python3
"""Run orchestration wrappers under the OpenClaw monitor registry plus bridge adapters.

Official location: openclaw/bridge/ (OpenClaw integration layer; not AINL core).

Usage:
  python3 openclaw/bridge/run_wrapper_ainl.py <name> [--dry-run] [--trace]

  Shims for legacy paths: scripts/run_wrapper_ainl.py

Dry-run: sets frame[\"dry_run\"] so adapters skip network/disk side effects; execution still proceeds.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Repo root: openclaw/bridge/ -> openclaw/ -> repo
_BRIDGE_DIR = Path(__file__).resolve().parent
ROOT = _BRIDGE_DIR.parent.parent
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine

from adapters.crm import CrmAdapter
from adapters.github import GitHubAdapter
from adapters.openclaw_defaults import DEFAULT_CRM_HEALTH_URL
from adapters.openclaw_integration import openclaw_monitor_registry
from adapters.openclaw_memory import OpenClawMemoryAdapter

import importlib.util

_ir_spec = importlib.util.spec_from_file_location("ainl_bridge_ir_cache", _BRIDGE_DIR / "ir_cache.py")
assert _ir_spec and _ir_spec.loader
_ir_mod = importlib.util.module_from_spec(_ir_spec)
_ir_spec.loader.exec_module(_ir_mod)
compile_source_cached = _ir_mod.compile_source_cached

_bspec = importlib.util.spec_from_file_location(
    "bridge_token_budget_adapter",
    _BRIDGE_DIR / "bridge_token_budget_adapter.py",
)
assert _bspec and _bspec.loader
_bmod = importlib.util.module_from_spec(_bspec)
_bspec.loader.exec_module(_bmod)
BridgeTokenBudgetAdapter = _bmod.BridgeTokenBudgetAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ainl.wrapper")

WRAPPERS = {
    "github-intelligence": ROOT / "scripts" / "wrappers" / "github-intelligence.ainl",
    "content-engine": ROOT / "scripts" / "wrappers" / "content-engine.ainl",
    "supervisor": ROOT / "scripts" / "wrappers" / "supervisor.ainl",
    "full-unification": ROOT / "examples" / "openclaw_full_unification.ainl",
    "token-budget-alert": _BRIDGE_DIR / "wrappers" / "token_budget_alert.ainl",
    "weekly-token-trends": _BRIDGE_DIR / "wrappers" / "weekly_token_trends.ainl",
    "ttl-memory-tuner": _BRIDGE_DIR / "wrappers" / "ttl_memory_tuner.ainl",
    "embedding-memory-pilot": _BRIDGE_DIR / "wrappers" / "embedding_memory_pilot.ainl",
    "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",
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
    reg.allow("bridge")
    reg.register("bridge", BridgeTokenBudgetAdapter())
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

    def _compile(src_text: str) -> dict:
        return AICodeCompiler(strict_mode=False, strict_reachability=False).compile(
            src_text, emit_graph=True
        )

    ir = compile_source_cached(path, _compile)
    errs = ir.get("errors") or []
    if errs:
        logger.error("Compile errors: %s", errs)
        sys.exit(2)

    reg = build_wrapper_registry()
    eng = RuntimeEngine(ir, adapters=reg, trace=trace, execution_mode="graph-preferred")
    frame: dict = {
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
