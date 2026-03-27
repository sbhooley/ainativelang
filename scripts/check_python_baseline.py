#!/usr/bin/env python3
"""Exit 1 if interpreter is below project baseline (pyproject.toml requires-python)."""
from __future__ import annotations

import sys

MIN = (3, 10)


def main() -> int:
    v = sys.version_info
    if v[:2] < MIN:
        print(
            "ERROR: ainl requires Python 3.10+ "
            "(project baseline; matches pyproject.toml requires-python)."
        )
        print("       Current: Python %d.%d.%d" % (v.major, v.minor, v.micro))
        print("       Executable:", sys.executable)
        print("       Fix (replace .venv if it was created with an older Python):")
        print("         rm -rf .venv")
        print(
            "         python3.11 -m venv .venv   # or python3.12 / pyenv; "
            "on macOS: brew install python@3.11"
        )
        print('         source .venv/bin/activate && pip install -e ".[dev,benchmark]"')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
