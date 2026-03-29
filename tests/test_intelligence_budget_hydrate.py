"""Tests for tooling/intelligence_budget_hydrate.py."""
from __future__ import annotations

import gc
import json
import os
import tempfile
from pathlib import Path

import pytest

from runtime.adapters.base import AdapterRegistry
from runtime.adapters.builtins import CoreBuiltinAdapter
from adapters.openclaw_integration import CacheAdapter
from runtime.adapters.memory import MemoryAdapter

from tooling.intelligence_budget_hydrate import (
    hydrate_budget_cache_from_rolling_memory,
    merge_token_budget_with_rolling,
)


def _registry(tmp_path: Path, db: Path, cache_json: Path) -> AdapterRegistry:
    os.environ["AINL_MEMORY_DB"] = str(db)
    os.environ["MONITOR_CACHE_JSON"] = str(cache_json)
    reg = AdapterRegistry(allowed=[
        "core", "memory", "cache",
    ])
    reg.register("core", CoreBuiltinAdapter())
    reg.register("memory", MemoryAdapter(db_path=str(db), valid_namespaces={"workflow", "intel"}))
    reg.register("cache", CacheAdapter())
    return reg


def test_merge_token_budget_with_rolling_fills_daily_when_missing() -> None:
    rolling = {
        "weekly_remaining_tokens": 7000,
        "avg_daily_tokens": 100,
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    m = merge_token_budget_with_rolling(None, rolling)
    assert m["rolling_weekly_remaining_tokens"] == 7000
    assert m["daily_remaining"] == 1000  # 7000 // 7


def test_merge_conservative_min_with_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AINL_INTELLIGENCE_ROLLING_CONSERVATIVE_DAILY", "1")
    rolling = {"weekly_remaining_tokens": 700, "updated_at_utc": "x"}
    m = merge_token_budget_with_rolling({"daily_remaining": 50000}, rolling)
    assert m["daily_remaining"] == 100  # min(50000, 700//7)


def test_hydrate_end_to_end(tmp_path: Path) -> None:
    cache_json = tmp_path / "cache.json"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3") as f:
        db_path = f.name
    ma = None
    reg = None
    try:
        Path(db_path).unlink(missing_ok=True)
        ma = MemoryAdapter(db_path=db_path, valid_namespaces={"workflow", "intel"})
        ma.call(
            "put",
            [
                "workflow",
                "budget.aggregate",
                "weekly_remaining_v1",
                {
                    "weekly_total_tokens": 100,
                    "avg_daily_tokens": 10,
                    "days_in_window": 7,
                    "weekly_cap_tokens": 10000,
                    "weekly_remaining_tokens": 7000,
                    "updated_at_utc": "2026-01-01T00:00:00Z",
                    "source": "test",
                },
                86400,
                {"tags": ["rolling_budget"]},
            ],
            {},
        )
        os.environ["AINL_MEMORY_DB"] = db_path
        os.environ["MONITOR_CACHE_JSON"] = str(cache_json)
        reg = AdapterRegistry(allowed=["core", "memory", "cache"])
        reg.register("core", CoreBuiltinAdapter())
        reg.register("memory", MemoryAdapter(db_path=db_path, valid_namespaces={"workflow", "intel"}))
        reg.register("cache", CacheAdapter())
        out = hydrate_budget_cache_from_rolling_memory(reg)
        assert out["ok"] is True
        assert out.get("skipped") is not True
        c = reg.call("cache", "get", ["workflow", "token_budget"], {})
        assert isinstance(c, dict)
        assert c.get("daily_remaining") == 1000
        assert c.get("rolling_source") == "memory.budget.aggregate.weekly_remaining_v1"
    finally:
        for ad in (ma, reg._adapters.get("memory") if reg else None):
            if ad is not None and hasattr(ad, "_conn"):
                try:
                    ad._conn.close()
                except Exception:
                    pass
        gc.collect()
        Path(db_path).unlink(missing_ok=True)


def test_hydrate_skipped_when_env_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AINL_INTELLIGENCE_SKIP_ROLLING_HYDRATE", "1")
    db = tmp_path / "x.sqlite3"
    reg = _registry(tmp_path, db, tmp_path / "c.json")
    out = hydrate_budget_cache_from_rolling_memory(reg)
    assert out["skipped"] is True
