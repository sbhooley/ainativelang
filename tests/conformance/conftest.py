from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402


def pytest_configure(config) -> None:  # pragma: no cover
    """Route conformance snapshots to tests/snapshots/conformance/.

    Syrupy stores snapshots under <test_dir>/<snapshot_dirname>. For conformance we
    want: tests/conformance/../snapshots/conformance (repo-published artifacts).
    """

    try:
        current = getattr(config.option, "snapshot_dirname", "__snapshots__")
        if str(current) == "__snapshots__":
            config.option.snapshot_dirname = "../snapshots/conformance"
    except Exception:
        pass


@pytest.fixture
def compiler_lossless() -> AICodeCompiler:
    """Lossless compile path for tokenizer round-trip tests.

    We intentionally keep strict mode disabled so the suite can safely tokenize/parse
    even inputs that would fail strict validation later.
    """

    return AICodeCompiler(strict_mode=False)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

