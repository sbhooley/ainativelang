"""FanoutAdapter: parallel registry calls via JSON plan list."""

from __future__ import annotations

import json

from adapters.fanout import FanoutAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.adapters.builtins import CoreBuiltinAdapter


def test_fanout_all_runs_core_adds():
    reg = AdapterRegistry()
    reg.register("core", CoreBuiltinAdapter())
    fan = FanoutAdapter()
    ctx = {"_adapter_registry": reg}
    plans = json.dumps([["core", "add", 1, 2], ["core", "add", 3, 4]])
    out = fan.call("ALL", [plans], ctx)
    assert out == [3, 7]
