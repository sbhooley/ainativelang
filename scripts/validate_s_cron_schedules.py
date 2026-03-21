#!/usr/bin/env python3
"""
Validate top-level `S` (service) lines that declare a cron schedule.

The compiler stores `S` as exactly three slots: service name, mode, path
(`compiler_v2.py`, `op == "S"`). For scheduled jobs the intended shape is::

    S <adapter> cron "<cron expression>"

If extra tokens appear before `cron` (e.g. ``S core memory cron "0 * * * *"``),
the expression is mis-parsed: `path` becomes the literal ``cron`` and the
schedule is lost from `ir["services"]`.

This script scans ``*.lang`` and ``*.ainl`` under the repo (skipping common
junk dirs) and fails if any `S` line contains the token ``cron`` but ``cron``
is not the **second** argument after ``S``.

Exit 0 when clean; non-zero with stderr messages when violations are found.

Usage::

    python3 scripts/validate_s_cron_schedules.py
    python3 scripts/validate_s_cron_schedules.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv-py310",
    ".venv-ci-smoke",
    "venv",
    "venv-py310",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}

S_LINE = re.compile(r"^\s*S\s+(.+?)\s*(?:#.*)?$")


def _iter_source_files() -> List[Path]:
    out: List[Path] = []
    for pattern in ("**/*.lang", "**/*.ainl"):
        for p in ROOT.glob(pattern):
            if not p.is_file():
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
                continue
            out.append(p)
    return sorted(out)


def _check_line(rel: str, lineno: int, line: str) -> str | None:
    m = S_LINE.match(line)
    if not m:
        return None
    rest = m.group(1).strip()
    try:
        parts = shlex.split(rest)
    except ValueError:
        return f"{rel}:{lineno}: cannot parse S line (shlex): {line.strip()!r}"
    if "cron" not in parts:
        return None
    if len(parts) < 2:
        return f"{rel}:{lineno}: S line too short: {line.strip()!r}"
    if parts[1] != "cron":
        return (
            f"{rel}:{lineno}: invalid S+cron shape — token after adapter must be "
            f"`cron`, got {parts[1]!r} (full: {line.strip()!r}). "
            f"Use `S <adapter> cron \"<expr>\"` only; do not insert adapter names "
            f"between the first token and `cron`."
        )
    return None


def run_check() -> Tuple[List[str], int]:
    errors: List[str] = []
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT))
        for i, line in enumerate(text.splitlines(), start=1):
            err = _check_line(rel, i, line)
            if err:
                errors.append(err)
    return errors, len(errors)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print machine-readable report")
    args = ap.parse_args()
    errors, n = run_check()
    if args.json:
        payload: Dict[str, Any] = {"ok": n == 0, "violation_count": n, "violations": errors}
        print(json.dumps(payload, indent=2))
    else:
        for e in errors:
            print(e, file=sys.stderr)
        if n:
            print(
                f"validate_s_cron_schedules: {n} violation(s). "
                "See docs/CRON_ORCHESTRATION.md § `S` line (cron).",
                file=sys.stderr,
            )
    return 1 if n else 0


if __name__ == "__main__":
    raise SystemExit(main())
