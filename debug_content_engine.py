#!/usr/bin/env python3
import sys, json, os
from pathlib import Path

ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine, run_with_debug
from adapters.openclaw_integration import openclaw_monitor_registry
from adapters.openclaw_memory import OpenClawMemoryAdapter
from adapters.github import GitHubAdapter
from adapters.crm import CrmAdapter
from openclaw.bridge.run_wrapper_ainl import compile_source_cached, BridgeTokenBudgetAdapter, _BRIDGE_DIR, build_wrapper_registry

# Load the IR with trace
path = ROOT / "scripts" / "wrappers" / "content-engine.ainl"
def _compile(src_text):
    return AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src_text, emit_graph=True)

ir = compile_source_cached(path, _compile)
if ir.get("errors"):
    print("Compile errors:", ir["errors"])
    sys.exit(1)

# Build adapters
reg = build_wrapper_registry()
frame = {
    "crm_health_url": "http://localhost:3000/health",
    "dry_run": True,
}
# Run with debug to get trace
result = run_with_debug(RuntimeEngine(ir, adapters=reg, trace=True, execution_mode="graph-preferred"), "0", frame)
print(json.dumps(result, indent=2, default=str))
