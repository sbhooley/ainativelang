from __future__ import annotations

import asyncio
import inspect
from typing import Any, Dict, Iterable, List, Optional, Set


class AdapterError(RuntimeError):
    pass


class RuntimeAdapter:
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        raise NotImplementedError

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        # Backward-compatible default: adapters can stay sync-only.
        return self.call(target=target, args=args, context=context)


class HttpAdapter(RuntimeAdapter):
    pass


class SqliteAdapter(RuntimeAdapter):
    pass


class FileSystemAdapter(RuntimeAdapter):
    pass


class ToolsAdapter(RuntimeAdapter):
    pass


class AdapterRegistry:
    """
    Adapter dispatch for runtime execution.
    call(adapter_name, target, args, context) -> value
    """

    def __init__(self, allowed: Optional[Iterable[str]] = None):
        self._adapters: Dict[str, RuntimeAdapter] = {}
        self._allowed: Set[str] = set(allowed or ["core"])

    def register(self, name: str, adapter: RuntimeAdapter) -> None:
        self._adapters[name] = adapter

    def allow(self, name: str) -> None:
        self._allowed.add(name)

    def deny(self, name: str) -> None:
        self._allowed.discard(name)

    def call(self, adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if adapter_name not in self._allowed:
            raise AdapterError(f"adapter blocked by capability gate: {adapter_name}")
        adp = self._adapters.get(adapter_name)
        if adp is None:
            raise AdapterError(f"adapter not registered: {adapter_name}")
        if self._async_enabled(context):
            call_async = getattr(adp, "call_async", None)
            if callable(call_async):
                return self._run_async(call_async(target=target, args=args, context=context))
        return adp.call(target=target, args=args, context=context)

    async def call_async(self, adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if adapter_name not in self._allowed:
            raise AdapterError(f"adapter blocked by capability gate: {adapter_name}")
        adp = self._adapters.get(adapter_name)
        if adp is None:
            raise AdapterError(f"adapter not registered: {adapter_name}")
        call_async = getattr(adp, "call_async", None)
        if callable(call_async):
            out = call_async(target=target, args=args, context=context)
            if inspect.isawaitable(out):
                return await out
            return out
        return adp.call(target=target, args=args, context=context)

    def _async_enabled(self, context: Dict[str, Any]) -> bool:
        if not isinstance(context, dict):
            return False
        return bool(context.get("_runtime_async"))

    def _run_async(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            try:
                return asyncio.run(maybe_awaitable)
            except RuntimeError as e:
                raise AdapterError(f"async adapter dispatch failed: {e}") from e
        return maybe_awaitable

    def _require(self, name: str) -> RuntimeAdapter:
        if name not in self._allowed:
            raise AdapterError(f"adapter blocked by capability gate: {name}")
        adp = self._adapters.get(name)
        if adp is None:
            raise AdapterError(f"adapter not registered: {name}")
        return adp

    def get_cache(self) -> RuntimeAdapter:
        return self._require("cache")

    def get_queue(self) -> RuntimeAdapter:
        return self._require("queue")

    def get_txn(self) -> RuntimeAdapter:
        return self._require("txn")

    def get_auth(self) -> RuntimeAdapter:
        return self._require("auth")

    def get_http(self) -> RuntimeAdapter:
        return self._require("http")

    def get_sqlite(self) -> RuntimeAdapter:
        return self._require("sqlite")

    def get_fs(self) -> RuntimeAdapter:
        return self._require("fs")

    def get_tools(self) -> RuntimeAdapter:
        return self._require("tools")
