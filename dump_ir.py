#!/usr/bin/env python3
import sys, json
from pathlib import Path

ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler
from openclaw.bridge.run_wrapper_ainl import compile_source_cached

path = ROOT / "scripts" / "wrappers" / "content-engine.ainl"
def _compile(src_text):
    return AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src_text, emit_graph=True)

ir = compile_source_cached(path, _compile)
print(json.dumps(ir, indent=2, default=str))
