#!/usr/bin/env python3
"""
Extension-only CLI for validating AINL memory records.

This script checks memory record envelopes against the v1 memory contract
defined in `docs/MEMORY_CONTRACT.md`. It does not change compiler/runtime
semantics and is intended as governance and compatibility tooling for advanced
memory usage.
"""

from tooling.memory_validator import main


if __name__ == "__main__":
    raise SystemExit(main())

