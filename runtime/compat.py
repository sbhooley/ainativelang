"""
Backward-compatible runtime facade.

Canonical execution semantics live in `runtime.engine` (`RuntimeEngine`).
This module preserves the historical `ExecutionEngine` API used by emitters and
user apps while delegating execution to the canonical engine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from compiler_v2 import runtime_normalize_label_id, runtime_normalize_node_id
from runtime.adapters.base import AdapterRegistry as RuntimeAdapterRegistry
from runtime.adapters.base import RuntimeAdapter
from runtime.engine import RuntimeEngine

from adapters import AdapterRegistry as LegacyAdapterRegistry


def _normalize_label_id(tgt: str) -> str:
    return runtime_normalize_label_id(tgt)


def _normalize_node_id(tok: Any) -> Optional[str]:
    return runtime_normalize_node_id(tok)


class _LegacyDbBridge(RuntimeAdapter):
    def __init__(self, db: Any):
        self.db = db

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").upper()
        entity = args[0] if len(args) > 0 else ""
        arg = args[1] if len(args) > 1 else "*"
        if verb == "F":
            return self.db.find(entity, arg)
        if verb == "G":
            return self.db.get(entity, arg)
        if verb == "P":
            payload = arg if isinstance(arg, dict) else {"value": arg}
            return self.db.create(entity, payload)
        if verb == "D":
            return self.db.delete(entity, arg)
        if verb == "Q":
            query = args[1] if len(args) > 1 else ""
            params = args[2] if len(args) > 2 else None
            partition = args[3] if len(args) > 3 else None
            query_fn = getattr(self.db, "query", None)
            if not callable(query_fn):
                raise RuntimeError("db.Q unsupported by this adapter")
            return query_fn(entity, query, params, partition)
        if verb == "M":
            doc_id = args[1] if len(args) > 1 else None
            patch = args[2] if len(args) > 2 else None
            etag = args[3] if len(args) > 3 else None
            merge_fn = getattr(self.db, "merge", None)
            if not callable(merge_fn):
                raise RuntimeError("db.M unsupported by this adapter")
            return merge_fn(entity, doc_id, patch if isinstance(patch, dict) else {}, etag)
        raise RuntimeError(f"unsupported db verb: {verb}")


class _LegacyApiBridge(RuntimeAdapter):
    def __init__(self, api: Any):
        self.api = api

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").upper()
        path = args[0] if len(args) > 0 else "/"
        body = args[1] if len(args) > 1 and isinstance(args[1], dict) else None
        if verb == "G":
            return self.api.get(path)
        if verb == "P":
            if not hasattr(self.api, "post"):
                raise RuntimeError("api.P unsupported by legacy adapter")
            return self.api.post(path, body)
        raise RuntimeError(f"unsupported api verb: {verb}")


def _bridge_legacy_adapters(legacy: LegacyAdapterRegistry) -> RuntimeAdapterRegistry:
    allowed = {"core"}
    reg = RuntimeAdapterRegistry(allowed=allowed)

    if getattr(legacy, "db", None) is not None:
        reg.register("db", _LegacyDbBridge(legacy.get_db()))
        reg.allow("db")
    if getattr(legacy, "api", None) is not None:
        reg.register("api", _LegacyApiBridge(legacy.get_api()))
        reg.allow("api")
    if getattr(legacy, "cache", None) is not None:
        reg.register("cache", legacy.get_cache())
        reg.allow("cache")
    if getattr(legacy, "queue", None) is not None:
        reg.register("queue", legacy.get_queue())
        reg.allow("queue")
    if getattr(legacy, "txn", None) is not None:
        reg.register("txn", legacy.get_txn())
        reg.allow("txn")
    if getattr(legacy, "auth", None) is not None:
        reg.register("auth", legacy.get_auth())
        reg.allow("auth")

    return reg


class ExecutionEngine:
    """
    Backward-compatible API shim over `runtime.engine.RuntimeEngine`.
    """

    def __init__(self, ir: Dict[str, Any], adapters: LegacyAdapterRegistry):
        self.ir = ir
        self.adapters = adapters
        self._runtime = RuntimeEngine(
            ir=ir,
            adapters=_bridge_legacy_adapters(adapters),
            trace=False,
            execution_mode=(ir.get("runtime_policy") or {}).get("execution_mode", "graph-preferred"),
            unknown_op_policy=(ir.get("runtime_policy") or {}).get("unknown_op_policy", "skip"),
        )

    def _get_steps(self, label: Dict[str, Any]) -> List[Dict[str, Any]]:
        leg = label.get("legacy", {})
        if leg and "steps" in leg:
            return leg["steps"]
        return label.get("steps", [])

    def run(self, label_id: str, initial_ctx: Optional[Dict[str, Any]] = None) -> Any:
        return self._runtime.run_label(_normalize_label_id(label_id), frame=dict(initial_ctx or {}))
