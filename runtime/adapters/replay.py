from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, AdapterRegistry


class RecordingAdapterRegistry(AdapterRegistry):
    def __init__(self, allowed: Optional[List[str]] = None):
        super().__init__(allowed=allowed)
        self.call_log: List[Dict[str, Any]] = []

    def call(self, adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        result = super().call(adapter_name, target, args, context)
        self.call_log.append(
            {
                "adapter": adapter_name,
                "target": target,
                "args": list(args),
                "result": result,
            }
        )
        return result


class ReplayAdapterRegistry(AdapterRegistry):
    def __init__(self, replay_log: List[Dict[str, Any]], allowed: Optional[List[str]] = None):
        super().__init__(allowed=allowed)
        self._replay_log = list(replay_log)
        self._idx = 0
        self.call_log: List[Dict[str, Any]] = []

    def call(self, adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if self._idx >= len(self._replay_log):
            raise AdapterError("replay exhausted: no recorded adapter call available")
        expected = self._replay_log[self._idx]
        actual_sig = {"adapter": adapter_name, "target": target, "args": list(args)}
        expected_sig = {"adapter": expected.get("adapter"), "target": expected.get("target"), "args": expected.get("args")}
        if actual_sig != expected_sig:
            raise AdapterError(f"replay mismatch: expected {expected_sig}, got {actual_sig}")
        result = expected.get("result")
        self.call_log.append(
            {
                "adapter": adapter_name,
                "target": target,
                "args": list(args),
                "result": result,
            }
        )
        self._idx += 1
        return result
