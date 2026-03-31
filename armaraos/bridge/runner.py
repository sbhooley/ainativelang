#!/usr/bin/env python3
"""Run orchestration wrappers under the OpenFang monitor registry plus bridge adapters.

Official location: armaraos/bridge/ (OpenFang integration layer; not AINL core).

Usage:
  python3 armaraos/bridge/run_wrapper_ainl.py <name> [--dry-run] [--trace]

  Shims for legacy paths: scripts/run_wrapper_ainl.py

Dry-run: sets frame[\"dry_run\"] so adapters skip network/disk side effects; execution still proceeds.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from tooling.capability_grant import load_profile_as_grant, grant_to_allowed_adapters, empty_grant

from typing import Any, Optional, Tuple

# Repo root: armaraos/bridge/ -> armaraos/ -> repo
_BRIDGE_DIR = Path(__file__).resolve().parent
ROOT = _BRIDGE_DIR.parent.parent
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine

from adapters.crm import CrmAdapter
from adapters.github import GitHubAdapter
from adapters.armaraos_defaults import DEFAULT_CRM_HEALTH_URL
from adapters.armaraos_integration import armaraos_monitor_registry
from adapters.armaraos_memory import OpenFangMemoryAdapter
from adapters.armaraos_token_tracker import OpenFangTokenTrackerAdapter

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
    "full-unification": ROOT / "examples" / "armaraos_full_unification.ainl",
    "token-budget-alert": _BRIDGE_DIR / "wrappers" / "token_budget_alert.ainl",
    "weekly-token-trends": _BRIDGE_DIR / "wrappers" / "weekly_token_trends.ainl",
    "ttl-memory-tuner": _BRIDGE_DIR / "wrappers" / "ttl_memory_tuner.ainl",
    "embedding-memory-pilot": _BRIDGE_DIR / "wrappers" / "embedding_memory_pilot.ainl",
    "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",
    "wasm-health-score": _BRIDGE_DIR / "wrappers" / "wasm_health_score.ainl",
    # OpenSpace integrations
    "lead-ai-openspace": ROOT / "demo" / "lead_ai_openspace.ainl",
    "ainl-wrapper-evolver": ROOT / "demo" / "ainl_wrapper_evolver.ainl",
    "test-openspace-mcp": ROOT / "demo" / "test_openspace_mcp.ainl",
    "test-simple": ROOT / "demo" / "test_simple.ainl",
    "test-mcp-log": ROOT / "demo" / "test_mcp_log.ainl",
    # "email-monitor": _BRIDGE_DIR / "wrappers" / "email_monitor.ainl",  # disabled: requires 'armaraos mail' plugin
}


# --- OpenFang Bridge Grant Validation ---
# The bridge runs with a fixed set of adapters. We ensure the active security
# profile (if any) allows all required adapters.
def _load_bridge_grant() -> dict:
    profile = os.environ.get("ARMARAOS_SECURITY_PROFILE")
    if profile:
        try:
            return load_profile_as_grant(profile)
        except ValueError as e:
            logger.error("Invalid ARMARAOS_SECURITY_PROFILE %s: %s", profile, e)
            return empty_grant()
    # Default: wide open (legacy behavior)
    return empty_grant()

_BRIDGE_GRANT = _load_bridge_grant()

# Set of adapter names the bridge needs to function
_REQUIRED_ADAPTERS = {
    "core",  # always required
    "armaraos_memory",
    "github",
    "crm",
    "armaraos_token_tracker",
    "bridge",
}

# Validate at import time (before main)
_allowed = set(grant_to_allowed_adapters(_BRIDGE_GRANT))
_missing = _REQUIRED_ADAPTERS - _allowed
if _missing:
    logger.error("OpenFang bridge missing required adapters due to security profile: %s", ", ".join(sorted(_missing)))
    logger.error("Set ARMARAOS_SECURITY_PROFILE to a grant that includes these adapters or unset to disable restriction.")
    sys.exit(1)


def _read_monitor_budget() -> dict:
    """Best-effort read of rolling budget from MONITOR_CACHE_JSON.

    This is an execution guard only; the bridge/intelligence stack remains the source of truth.
    """
    path = Path(os.environ.get("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    wf = obj.get("workflow") if isinstance(obj, dict) else None
    tb = wf.get("token_budget") if isinstance(wf, dict) else None
    return tb if isinstance(tb, dict) else {}


def _should_skip_wrapper(name: str) -> Optional[dict]:
    """Skip noncritical wrappers when budgets are low.

    This keeps scheduled bridge jobs from spending tokens when a host is already near exhaustion.
    """
    critical = {"token-budget-alert", "content-engine"}
    if name in critical:
        return None
    tb = _read_monitor_budget()
    if not tb:
        return None
    try:
        day_rem = tb.get("daily_remaining")
        week_rem = tb.get("weekly_remaining_tokens")
        min_day = int(os.environ.get("AINL_WRAPPER_MIN_DAILY_REMAINING", "1000"))
        min_week = int(os.environ.get("AINL_WRAPPER_MIN_WEEKLY_REMAINING", "5000"))

        # Optional per-wrapper overrides via JSON:
        # AINL_WRAPPER_BUDGET_GUARDS_JSON='{"weekly-token-trends":{"min_weekly":10000},"ttl-memory-tuner":{"skip":true}}'
        guards_raw = (os.environ.get("AINL_WRAPPER_BUDGET_GUARDS_JSON") or "").strip()
        if guards_raw:
            try:
                guards = json.loads(guards_raw)
                if isinstance(guards, dict) and isinstance(guards.get(name), dict):
                    g = guards[name]
                    if g.get("skip") in (True, 1, "1", "true", "yes", "True"):
                        return {"reason": "wrapper_forced_skip", "guard": g}
                    if g.get("min_daily") is not None:
                        min_day = int(g["min_daily"])
                    if g.get("min_weekly") is not None:
                        min_week = int(g["min_weekly"])
            except Exception:
                pass

        if week_rem is not None and int(week_rem) < min_week:
            return {"reason": "weekly_budget_low", "weekly_remaining_tokens": int(week_rem), "min_weekly": min_week}
        if day_rem is not None and int(day_rem) < min_day:
            return {"reason": "daily_budget_low", "daily_remaining": int(day_rem), "min_daily": min_day}
    except Exception:
        return None
    return None


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
    reg = armaraos_monitor_registry()
    for name in ("armaraos_memory", "github", "crm", "armaraos_token_tracker"):
        reg.allow(name)
    reg.register("armaraos_memory", OpenFangMemoryAdapter())
    reg.register("github", GitHubAdapter())
    reg.register("crm", CrmAdapter())
    reg.register("armaraos_token_tracker", OpenFangTokenTrackerAdapter())
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

    skip = _should_skip_wrapper(name)
    if skip:
        payload = {"ok": True, "wrapper": name, "skipped": True, "skip": skip}
        print(json.dumps(payload, indent=2, default=str))
        return

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
