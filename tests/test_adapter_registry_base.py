"""Unit tests for runtime.adapters.base.AdapterRegistry (public dict-like helpers)."""

from __future__ import annotations

from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.adapters.replay import RecordingAdapterRegistry, ReplayAdapterRegistry


class _NoopAdapter(RuntimeAdapter):
    def call(self, target, args, context):
        return None


def test_adapter_registry_keys_empty_when_no_registrations():
    reg = AdapterRegistry(allowed=["core", "alpha"])
    assert list(reg.keys()) == []


def test_adapter_registry_keys_lists_registered_names():
    reg = AdapterRegistry(allowed=["core", "a", "b"])
    reg.register("a", _NoopAdapter())
    reg.register("b", _NoopAdapter())
    assert set(reg.keys()) == {"a", "b"}
    assert "a" in reg.keys()
    assert sorted(reg.keys()) == ["a", "b"]


def test_adapter_registry_keys_core_builtin():
    reg = AdapterRegistry(allowed=["core"])
    reg.register("core", CoreBuiltinAdapter())
    assert list(reg.keys()) == ["core"]


def test_recording_adapter_registry_keys_inherited():
    reg = RecordingAdapterRegistry(allowed=["core", "x"])
    reg.register("x", _NoopAdapter())
    assert set(reg.keys()) == {"x"}


def test_replay_adapter_registry_keys_inherited():
    reg = ReplayAdapterRegistry([], allowed=["core", "y"])
    reg.register("y", _NoopAdapter())
    assert set(reg.keys()) == {"y"}
