"""Unit tests for core.merge (shallow dict merge)."""

from runtime.adapters.builtins import CoreBuiltinAdapter


def test_core_merge_two_dicts():
    a = CoreBuiltinAdapter()
    assert a.call("merge", [{"a": 1}, {"b": 2}], {}) == {"a": 1, "b": 2}


def test_core_merge_later_wins():
    a = CoreBuiltinAdapter()
    assert a.call("merge", [{"a": 1}, {"a": 2}], {}) == {"a": 2}


def test_core_merge_skips_non_dict():
    a = CoreBuiltinAdapter()
    assert a.call("merge", [{"a": 1}, "skip", {"b": 2}], {}) == {"a": 1, "b": 2}


def test_core_len_string():
    a = CoreBuiltinAdapter()
    assert a.call("len", ["abc"], {}) == 3
    assert a.call("len", [""], {}) == 0
