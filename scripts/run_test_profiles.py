#!/usr/bin/env python3
"""
Run named test profiles for CI/local workflows.

Profiles:
  - core: default stable suite (fast, no integration/emits/lsp)
  - emits: emitted artifact syntax checks
  - lsp: language server script smoke test
  - integration: emits + lsp
  - full: core + integration
  - openclaw: validate monitor_system.lang and check OpenClaw adapter registry
  - docs: run documentation contract checks
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import List


def _run(cmd: List[str], cwd: str) -> int:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd).returncode


def _load_json_file(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--profile",
        choices=["core", "emits", "lsp", "integration", "full", "openclaw", "docs"],
        default="core",
        help="which test profile to run",
    )
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py = sys.executable
    core_ignores = [
        "--ignore=tests/conformance",
        "--ignore=tests/test_bridge_shims.py",
        "--ignore=tests/test_visualizer.py",
        "--ignore=tests/test_zeroclaw_wrappers.py",
        "--ignore=tests/test_artifact_policy_manifest.py",
        "--ignore=tests/test_agent_send_task.py",
        "--ignore=tests/test_apollo_x_gateway.py",
        "--ignore=tests/test_install_openclaw.py",
        "--ignore=tests/test_install_zeroclaw.py",
        "--ignore=tests/test_sqlite_adapter_contracts.py",
    ]

    if args.profile == "core":
        rc = _run(
            [py, "-m", "pytest", "-q", "-m", "not integration and not emits and not lsp", *core_ignores],
            root,
        )
        raise SystemExit(rc)

    if args.profile == "emits":
        rc = _run([py, "-m", "pytest", "-q", "tests/test_emits_artifacts.py", "-m", "emits"], root)
        raise SystemExit(rc)

    if args.profile == "lsp":
        rc = _run([py, "scripts/test_lsp.py"], root)
        raise SystemExit(rc)

    if args.profile == "integration":
        rc1 = _run([py, "-m", "pytest", "-q", "tests/test_emits_artifacts.py", "-m", "integration"], root)
        if rc1 != 0:
            raise SystemExit(rc1)
        rc2 = _run([py, "scripts/test_lsp.py"], root)
        raise SystemExit(rc2)

    if args.profile == "openclaw":
        # Validate the monitor demo compiles in compatibility mode and adapter registry includes OpenClaw adapters.
        rc1 = _run(
            [py, "scripts/validate_ainl.py", "demo/monitor_system.lang"],
            root,
        )
        if rc1 != 0:
            print("OpenClaw profile: monitor_system.lang validation FAILED")
            raise SystemExit(rc1)
        # Check ADAPTER_REGISTRY.json has required OpenClaw adapters
        reg = _load_json_file(os.path.join(root, "ADAPTER_REGISTRY.json"))
        required = ["email", "calendar", "social", "db", "svc", "cache", "queue", "wasm"]
        missing = [a for a in required if a not in reg.get("adapters", {})]
        if missing:
            print(f"OpenClaw profile: missing adapters in registry: {missing}")
            raise SystemExit(1)
        print("OpenClaw profile: all required adapters present in registry")
        # Optionally, could run a smoke test of the monitor in dry-run mode if supported
        raise SystemExit(0)

    if args.profile == "docs":
        rc = _run([py, "scripts/check_docs_contracts.py", "--scope", "all"], root)
        raise SystemExit(rc)

    # full
    rc1 = _run(
        [py, "-m", "pytest", "-q", "-m", "not integration and not emits and not lsp", *core_ignores],
        root,
    )
    if rc1 != 0:
        raise SystemExit(rc1)
    rc2 = _run([py, "-m", "pytest", "-q", "tests/test_emits_artifacts.py", "-m", "integration"], root)
    if rc2 != 0:
        raise SystemExit(rc2)
    rc3 = _run([py, "scripts/test_lsp.py"], root)
    raise SystemExit(rc3)


if __name__ == "__main__":
    main()
