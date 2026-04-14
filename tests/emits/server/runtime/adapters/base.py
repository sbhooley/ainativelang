from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


class AdapterError(RuntimeError):
    pass


class RuntimeAdapter:
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        raise NotImplementedError


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

    def get(self, name: str) -> Optional[RuntimeAdapter]:
        """Return the registered adapter instance, or ``None`` if not registered."""
        return self._adapters.get(name)

    def keys(self):
        return self._adapters.keys()

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._adapters

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
        return adp.call(target=target, args=args, context=context)

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
