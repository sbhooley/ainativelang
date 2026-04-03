"""File-backed key/value cache for `ainl run` (no OpenClaw dependency).

Env (first match wins):
  AINL_CACHE_JSON — preferred
  MONITOR_CACHE_JSON — legacy (OpenClaw monitor cache path)

Default: ``~/.openclaw/ainl_cache.json``

Verbs: ``get``, ``set`` — see :meth:`LocalFileCacheAdapter.call`.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from runtime.adapters.base import AdapterError, RuntimeAdapter

logger = logging.getLogger(__name__)


def _default_cache_path() -> str:
    raw = (os.environ.get("AINL_CACHE_JSON") or os.environ.get("MONITOR_CACHE_JSON") or "").strip()
    if raw:
        return raw
    return str(Path.home() / ".openclaw" / "ainl_cache.json")


class LocalFileCacheAdapter(RuntimeAdapter):
    """Namespace + key JSON file store; supports single-key shorthand for ergonomics."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or _default_cache_path()
        self.store: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self.store = json.load(f)
                if not isinstance(self.store, dict):
                    self.store = {}
        except (FileNotFoundError, json.JSONDecodeError):
            self.store = {}

    def _save(self) -> None:
        try:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.store, f)
        except OSError as e:
            logger.warning("cache save error: %s", e)

    def get(self, namespace: str, key: str) -> Any:
        return self.store.get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any, ttl_s: int = 0) -> None:
        self.store.setdefault(namespace, {})[key] = value
        self._save()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").lower()
        if verb == "get":
            if len(args) == 1:
                return self.get("default", str(args[0]))
            if len(args) >= 2:
                return self.get(str(args[0]), str(args[1]))
            raise AdapterError("cache.get requires key or namespace and key")
        if verb == "set":
            if len(args) == 2:
                self.set("default", str(args[0]), args[1])
                return None
            if len(args) >= 3:
                self.set(str(args[0]), str(args[1]), args[2])
                return None
            raise AdapterError("cache.set requires key and value or namespace, key, and value")
        raise AdapterError("cache supports get/set")


# Backward-compatible alias for OpenClaw integration and tests.
CacheAdapter = LocalFileCacheAdapter
