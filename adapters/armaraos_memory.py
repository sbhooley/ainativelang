"""ArmaraOS daily markdown memory bridge.

This mirrors the OpenClaw daily memory adapter shape (append_today/read_today/search)
but uses ArmaraOS workspace defaults and env aliases.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from armaraos.env import resolve_armaraos_env
from runtime.adapters.base import RuntimeAdapter, AdapterError

logger = logging.getLogger(__name__)


def _dry_run(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes", "on"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on")


def _memory_dir() -> Path:
    # Allow explicit overrides, but default to ArmaraOS workspace/memory
    override = os.getenv("ARMARAOS_MEMORY_DIR") or os.getenv("ARMARAOS_DAILY_MEMORY_DIR")
    if override:
        return Path(override).expanduser()
    return resolve_armaraos_env().memory_dir


def _daily_path() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _memory_dir() / f"{day}.md"


class OpenFangMemoryAdapter(RuntimeAdapter):
    """
    Adapter group: armaraos_memory
    Verbs: append_today, read_today, search

    Note: class name kept for backward compatibility with earlier ArmaraOS/OpenFang bridge scripts.
    """

    _SEARCH_CACHE_TTL_S = 90

    def __init__(self) -> None:
        self._cache_path = Path(os.getenv("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = _dry_run(context)

        if verb == "append_today":
            if len(args) < 1:
                raise AdapterError("append_today requires text: str")
            text = str(args[0])
            if dry:
                logger.info("[dry_run] armaraos_memory.append_today — no write")
                return 1
            path = _daily_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            line = f"- {iso} — {text}\n"
            day = path.stem
            if not path.exists():
                header = f"# Memory Log - {day}\n\n## AINL · ArmaraOS bridge\n\n"
                path.write_text(header + line, encoding="utf-8")
            else:
                body = path.read_text(encoding="utf-8", errors="replace")
                if "## AINL · ArmaraOS bridge" not in body:
                    body = body.rstrip() + "\n\n## AINL · ArmaraOS bridge\n\n"
                body = body.rstrip() + "\n" + line
                path.write_text(body + "\n", encoding="utf-8")
            return 1

        if verb == "read_today":
            path = _daily_path()
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8", errors="replace")

        if verb == "search":
            if len(args) < 1:
                raise AdapterError("search requires query: str")
            query = str(args[0])
            max_results = int(args[1]) if len(args) >= 2 else 20
            days_back = int(args[2]) if len(args) >= 3 else 14

            ck = hashlib.sha256(f"{query}|{max_results}|{days_back}".encode("utf-8")).hexdigest()[:24]
            cached = self._cache_get("armaraos_memory_search", ck)
            if isinstance(cached, dict):
                ts = float(cached.get("ts", 0))
                if time.time() - ts < self._SEARCH_CACHE_TTL_S:
                    return cached.get("results", [])
            if dry:
                logger.info("[dry_run] armaraos_memory.search — no scan")
                return []

            results: list[dict] = []
            base = _memory_dir()
            now = datetime.now(timezone.utc)
            q = query.lower()
            for i in range(max(1, days_back)):
                day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                p = base / f"{day}.md"
                if not p.is_file():
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                for ln, line in enumerate(text.splitlines(), start=1):
                    if q in line.lower():
                        results.append({"path": str(p), "line": ln, "text": line.strip()[:500]})
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            self._cache_set("armaraos_memory_search", ck, {"ts": time.time(), "results": results})
            return results

        raise AdapterError(f"armaraos_memory: unknown verb {verb!r}")

    def _cache_load(self) -> Dict[str, Any]:
        try:
            import json

            if self._cache_path.is_file():
                obj = json.loads(self._cache_path.read_text(encoding="utf-8"))
                return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        return {}

    def _cache_save(self, data: Dict[str, Any]) -> None:
        try:
            import json

            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            logger.warning("armaraos_memory cache save failed: %s", e)

    def _cache_get(self, namespace: str, key: str) -> Any:
        return self._cache_load().get(namespace, {}).get(key)

    def _cache_set(self, namespace: str, key: str, value: Any) -> None:
        data = self._cache_load()
        data.setdefault(namespace, {})[key] = value
        self._cache_save(data)


# Alias for readability in new code.
ArmaraOSMemoryAdapter = OpenFangMemoryAdapter

