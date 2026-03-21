from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402


@pytest.fixture
def compiler_lossless() -> AICodeCompiler:
    """Lossless compile path for tokenizer round-trip tests.

    We intentionally keep strict mode disabled so the suite can safely tokenize/parse
    even inputs that would fail strict validation later.
    """

    return AICodeCompiler(strict_mode=False)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

