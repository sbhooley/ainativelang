"""Unit tests for core.contains (substring, empty needle)."""

from runtime.adapters.builtins import CoreBuiltinAdapter


def test_core_contains_basic():
    a = CoreBuiltinAdapter()
    assert a.call("contains", ["Hello world", "world"], {}) is True
    assert a.call("contains", ["Hello world", "World"], {}) is False
    assert a.call("contains", ["", "x"], {}) is False


def test_core_contains_empty_needle():
    a = CoreBuiltinAdapter()
    assert a.call("contains", ["anything", ""], {}) is True


def test_core_contains_unicode():
    a = CoreBuiltinAdapter()
    assert a.call("contains", ["café", "caf"], {}) is True
