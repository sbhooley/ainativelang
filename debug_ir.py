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
print("IR keys:", ir.keys())
print("Labels:", list(ir.get("labels", {}).keys()))
print("Graph nodes count:", len(ir.get("graph", {}).get("nodes", [])))
# Show nodes for label 0
label0 = ir.get("labels", {}).get("0", {})
print("Label 0 entry_node:", label0.get("entry_node"))
print("Label 0 nodes:", label0.get("nodes", []))
