#!/usr/bin/env python3
"""Validate all examples/*.lang via validator CLI compile path."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def main() -> None:
    files = sorted(glob.glob("examples/*.lang"))
    compiler = AICodeCompiler()
    failed = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                code = fh.read()
            ir = compiler.compile(code)
            if ir.get("errors"):
                print(f"[FAIL] {f}: {ir['errors'][:3]}")
                failed += 1
            else:
                print(f"[OK]   {f}")
        except Exception as e:
            print(f"[FAIL] {f}: {e}")
            failed += 1
    if failed:
        raise SystemExit(1)
    print(f"validated {len(files)} examples")


if __name__ == "__main__":
    main()
