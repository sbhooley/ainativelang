#!/usr/bin/env python3
"""
Run AINL test blocks (Tst/Mock) from IR. Loads ir.json, runs each test label with optional mocks.
Usage: python scripts/run_ainl_tests.py [path/to/ir.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from runtime import ExecutionEngine
from adapters import mock_registry


def main():
    ir_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "tests", "emits", "server", "ir.json")
    if not os.path.isfile(ir_path):
        print(f"IR not found: {ir_path}", file=sys.stderr)
        sys.exit(1)
    with open(ir_path) as f:
        ir = json.load(f)
    tests = ir.get("tests", [])
    if not tests:
        print("No tests in IR.")
        sys.exit(0)
    registry = mock_registry(ir.get("types"))
    engine = ExecutionEngine(ir, registry)
    failed = 0
    for t in tests:
        label = t.get("label")
        if not label:
            continue
        mocks = t.get("mocks", [])
        # TODO: apply mocks to registry (override adapter responses) when adapter supports it
        try:
            result = engine.run(label)
            print(f"  OK  {label} -> {type(result).__name__}")
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            failed += 1
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
