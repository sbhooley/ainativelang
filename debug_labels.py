#!/usr/bin/env python3
import sys, json
from pathlib import Path

ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler

path = ROOT / "scripts" / "wrappers" / "content-engine.ainl"
def _compile(src_text):
    return AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src_text, emit_graph=True)

ir = _compile(path.read_text())
labels = ir.get("labels", {})
for lbl, info in labels.items():
    if lbl != "0":
        print(f"\nLabel {lbl}:")
        print("  Entry node:", info.get("entry_node"))
        print("  Node count:", len(info.get("nodes", [])))
        for n in info.get("nodes", [])[:5]:
            print(f"    {n['id']}: op={n['op']} data={n.get('data')}")
        if len(info.get("nodes", [])) > 5:
            print("    ...")
