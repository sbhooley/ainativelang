#!/usr/bin/env python3
"""
Documentation contract checker for human + AI contributor workflows.

Goals:
- Keep canonical docs cross-linked and current.
- Prevent stale transitional wording drift.
- Enforce required docs-touch coupling when semantics-critical code changes.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

SEMANTICS_CRITICAL_CODE_PATHS = {
    "compiler_v2.py",
    "runtime.py",
    "runtime/engine.py",
    "runtime/compat.py",
    "tooling/graph_normalize.py",
    "tooling/effect_analysis.py",
}

REQUIRED_DOCS_FOR_SEMANTICS = {
    "docs/RUNTIME_COMPILER_CONTRACT.md",
    "docs/CONFORMANCE.md",
    "docs/CHANGELOG.md",
    "README.md",
}

REQUIRED_LINKS = {
    "README.md": [
        "docs/DOCS_INDEX.md",
        "docs/RUNTIME_COMPILER_CONTRACT.md",
        "docs/DOCS_MAINTENANCE.md",
    ],
    "docs/DOCS_INDEX.md": [
        "docs/RUNTIME_COMPILER_CONTRACT.md",
        "docs/DOCS_MAINTENANCE.md",
    ],
    # Note: docs/AI_AGENT_CONTINUITY.md was moved to docs/agents/continuity.md
    # (see PR consolidating agent guides). The original path is a stub redirect.
    "docs/agents/continuity.md": [
        "docs/RUNTIME_COMPILER_CONTRACT.md",
        "docs/DOCS_MAINTENANCE.md",
    ],
    "docs/CONTRIBUTING_AI_AGENTS.md": [
        "docs/RUNTIME_COMPILER_CONTRACT.md",
        "docs/DOCS_MAINTENANCE.md",
    ],
}

STALE_PHRASES = [
    "graph execution planned",
    "runtime executes steps not graph",
    "until (1) and (2) are done",
    "invariant is aspirational",
]

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _run_git(args: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "").strip()


def _changed_files(base_ref: str | None) -> Set[str]:
    if base_ref:
        rc, out = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"])
        if rc == 0:
            return {line.strip() for line in out.splitlines() if line.strip()}
        return set()

    rc, out = _run_git(["status", "--porcelain"])
    if rc != 0:
        return set()
    changed: Set[str] = set()
    for line in out.splitlines():
        if not line:
            continue
        payload = line[3:].strip() if len(line) > 3 else ""
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1].strip()
        if payload:
            changed.add(payload)
    return changed


def _iter_docs() -> Iterable[Path]:
    yield from sorted(DOCS_DIR.rglob("*.md"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_required_links(errors: List[str]) -> None:
    for rel_path, required_targets in REQUIRED_LINKS.items():
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            errors.append(f"Missing required file for link checks: {rel_path}")
            continue
        content = _read(full_path)
        for target in required_targets:
            if target not in content:
                errors.append(f"{rel_path}: missing required link target text `{target}`")


def _check_docs_internal_link_style(errors: List[str]) -> None:
    for doc_path in _iter_docs():
        rel = doc_path.relative_to(REPO_ROOT).as_posix()
        content = _read(doc_path)
        for link in LINK_RE.findall(content):
            t = link.strip()
            if not t or t.startswith("#") or "://" in t or t.startswith("mailto:"):
                continue
            # Docs-internal markdown should be relative, not docs/... prefixed
            if t.startswith("docs/"):
                errors.append(f"{rel}: docs-internal link should be relative, found `{t}`")


def _check_stale_phrases(errors: List[str]) -> None:
    for doc_path in _iter_docs():
        rel = doc_path.relative_to(REPO_ROOT).as_posix()
        text = _read(doc_path).lower()
        for phrase in STALE_PHRASES:
            if phrase in text:
                errors.append(f"{rel}: stale phrase found `{phrase}`")


def _check_semantics_docs_coupling(changed: Set[str], errors: List[str]) -> None:
    if not changed:
        return
    if not any(p in changed for p in SEMANTICS_CRITICAL_CODE_PATHS):
        return
    missing = sorted(REQUIRED_DOCS_FOR_SEMANTICS - changed)
    if missing:
        errors.append(
            "Semantics-critical code changed without required docs updates. "
            f"Missing: {', '.join(missing)}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Check docs contract consistency.")
    ap.add_argument(
        "--scope",
        choices=["all", "changed"],
        default="changed",
        help="all: repository-wide checks; changed: adds code/docs coupling checks based on git diff/status",
    )
    ap.add_argument(
        "--base-ref",
        default=None,
        help="git base ref for changed-file detection (example: origin/main)",
    )
    args = ap.parse_args()

    errors: List[str] = []
    warnings: List[str] = []

    changed = _changed_files(args.base_ref) if args.scope == "changed" else set()
    if args.scope == "changed" and not changed:
        warnings.append(
            "No changed files detected for coupling checks; ran global docs checks only."
        )

    _check_required_links(errors)
    _check_docs_internal_link_style(errors)
    _check_stale_phrases(errors)

    if args.scope == "changed":
        _check_semantics_docs_coupling(changed, errors)

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")

    if errors:
        print("Documentation contract check FAILED:")
        for e in errors:
            print(f"- {e}")
        raise SystemExit(1)

    print("Documentation contract check passed.")


if __name__ == "__main__":
    main()
