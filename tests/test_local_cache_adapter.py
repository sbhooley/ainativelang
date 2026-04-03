"""Tests for adapters/local_cache.py (file-backed cache + shorthand)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from adapters.local_cache import LocalFileCacheAdapter


def test_cache_shorthand_get_set(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    os.environ["AINL_CACHE_JSON"] = str(p)
    try:
        ad = LocalFileCacheAdapter()
        assert ad.call("get", ["mykey"], {}) is None
        ad.call("set", ["mykey", {"a": 1}], {})
        assert ad.call("get", ["mykey"], {}) == {"a": 1}
        ad.call("set", ["ns", "k2", 42], {})
        assert ad.call("get", ["ns", "k2"], {}) == 42
    finally:
        os.environ.pop("AINL_CACHE_JSON", None)


def test_cache_persists_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "c2.json"
    os.environ["AINL_CACHE_JSON"] = str(p)
    try:
        LocalFileCacheAdapter().call("set", ["x", 99], {})
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["default"]["x"] == 99
    finally:
        os.environ.pop("AINL_CACHE_JSON", None)
