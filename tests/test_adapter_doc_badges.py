"""Tests for `scripts/refresh_adapter_doc_badges.py` (LONG_TERM_FIXES_TRACKER T3.2).

Verifies the invariants that protect the adapter-tier-badge propagation:

* Every doc that should be stamped IS stamped (no silent drift).
* Skip-list files are NEVER touched.
* The badge block is **idempotent** — re-running with the same registry
  state produces a byte-identical file.
* `--check` exits 0 when in sync and 1 when out of sync (the CI contract).
* Every rendered badge reflects the registry's `tier` field exactly.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "refresh_adapter_doc_badges.py"
REGISTRY = REPO_ROOT / "ADAPTER_REGISTRY.json"
ADAPTER_DOCS = REPO_ROOT / "docs" / "adapters"

# Mirror of the script's SKIP_FILES — kept in sync intentionally so the test
# fails loudly if anyone changes the skip list without thinking it through.
SKIP_FILES = {
    "README.md",
    "ADAPTER_TIERS.md",
    "CONTRACT_AND_COMPILER.md",
    "OPENCLAW_ADAPTERS.md",
}

FENCE_RE = re.compile(
    r"<!--\s*adapter-badge:begin[^>]*-->.*?<!--\s*adapter-badge:end\s*-->",
    re.DOTALL,
)


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _stamped_doc_paths() -> list[Path]:
    return [p for p in sorted(ADAPTER_DOCS.glob("*.md")) if p.name not in SKIP_FILES]


def test_check_passes_on_current_tree() -> None:
    """The committed tree must be in sync with the registry."""
    result = _run_script("--check")
    assert result.returncode == 0, (
        f"`refresh_adapter_doc_badges.py --check` failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"Run `python3 scripts/refresh_adapter_doc_badges.py` and commit."
    )


def test_every_non_skip_doc_has_a_badge() -> None:
    for path in _stamped_doc_paths():
        text = path.read_text(encoding="utf-8")
        assert FENCE_RE.search(text), (
            f"{path.relative_to(REPO_ROOT)} is missing the adapter-badge fence. "
            "Run `python3 scripts/refresh_adapter_doc_badges.py`."
        )


def test_skip_files_have_no_badge() -> None:
    for name in SKIP_FILES:
        p = ADAPTER_DOCS / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        assert not FENCE_RE.search(text), (
            f"{p.relative_to(REPO_ROOT)} should NOT have an adapter-badge fence "
            "(it is in SKIP_FILES); the script must never touch this file."
        )


def test_badge_reflects_registry_tier(tmp_path: Path) -> None:
    """Spot-check: each stamped doc's badge contains the tier label that
    matches the registry entry for that adapter."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    adapters = registry["adapters"]

    # filename -> registry key resolver (matches the script)
    explicit = {
        "MEMORY_CONTRACT.md": "memory",
        "MEMORY_CONTRACT_V1_1_RFC.md": "memory",
    }

    for path in _stamped_doc_paths():
        key = explicit.get(path.name) or path.name[:-3].lower()
        if key not in adapters:
            pytest.fail(
                f"{path.relative_to(REPO_ROOT)} has no registry entry under "
                f"`{key}`; either fix the filename->key mapping in the script "
                "or remove the doc."
            )
        tier = str(adapters[key].get("tier", "")).lower()
        text = path.read_text(encoding="utf-8")
        fence = FENCE_RE.search(text)
        assert fence is not None
        block = fence.group(0)
        if tier == "core":
            assert "**Core**" in block, (
                f"{path.relative_to(REPO_ROOT)} badge does not say **Core** "
                f"but the registry tier is `core`."
            )
        elif tier == "extended":
            assert "**Extended**" in block, (
                f"{path.relative_to(REPO_ROOT)} badge does not say **Extended** "
                f"but the registry tier is `extended`."
            )


def test_script_is_idempotent() -> None:
    """Running the writer twice produces a byte-identical tree."""
    # Snapshot current state.
    before = {p: p.read_text(encoding="utf-8") for p in _stamped_doc_paths()}
    # Run the writer twice.
    r1 = _run_script()
    assert r1.returncode == 0, r1.stderr
    after_first = {p: p.read_text(encoding="utf-8") for p in _stamped_doc_paths()}
    r2 = _run_script()
    assert r2.returncode == 0, r2.stderr
    after_second = {p: p.read_text(encoding="utf-8") for p in _stamped_doc_paths()}
    # Restore the original tree (we don't want side effects on the working copy).
    for p, original in before.items():
        if p.read_text(encoding="utf-8") != original:
            p.write_text(original, encoding="utf-8")
    assert after_first == after_second, (
        "second run of refresh_adapter_doc_badges.py produced different output "
        "than the first; the script is not idempotent."
    )


def test_check_detects_drift() -> None:
    """If a doc's badge is mutated to disagree with the registry, --check
    must exit 1."""
    targets = _stamped_doc_paths()
    if not targets:
        pytest.skip("no stamped adapter docs to mutate")
    victim = targets[0]
    original = victim.read_text(encoding="utf-8")
    try:
        # Corrupt the badge by replacing the tier label.
        corrupted = original.replace("**Core**", "**Premium**", 1)
        corrupted = corrupted.replace("**Extended**", "**Premium**", 1)
        # Ensure we actually changed something.
        assert corrupted != original, (
            "victim file had neither **Core** nor **Extended** in its badge; "
            "test setup is wrong."
        )
        victim.write_text(corrupted, encoding="utf-8")
        result = _run_script("--check")
        assert result.returncode == 1, (
            f"--check should have detected drift in {victim.name}; "
            f"got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    finally:
        victim.write_text(original, encoding="utf-8")
