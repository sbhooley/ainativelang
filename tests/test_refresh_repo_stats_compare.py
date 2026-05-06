"""Regression: refresh_repo_stats --check must not fail only because stats_refreshed (UTC) differs."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "refresh_repo_stats.py"


@pytest.fixture(scope="module")
def refresh_module():
    spec = importlib.util.spec_from_file_location("refresh_repo_stats", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["refresh_repo_stats"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_normalize_strips_stats_refreshed_for_compare(refresh_module):
    norm = refresh_module._normalize_status_yaml_for_repo_stats_compare
    a = (
        "# STATUS.yaml — What is real vs aspirational\n"
        "# stats_refreshed: 1999-01-01 (UTC) — run: python scripts/refresh_repo_stats.py\n"
        "\n"
        "real_and_working:\n"
        "  x: 1\n"
    )
    b = (
        "# STATUS.yaml — What is real vs aspirational\n"
        "# stats_refreshed: 2030-12-31 (UTC) — run: python scripts/refresh_repo_stats.py\n"
        "\n"
        "real_and_working:\n"
        "  x: 1\n"
    )
    assert norm(a) == norm(b)
