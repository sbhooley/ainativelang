"""OpenClaw daily markdown memory bridge: day files, CLI search, monitor cache for search."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter, AdapterError

logger = logging.getLogger(__name__)

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "/Users/clawdbot/.nvm/versions/node/v22.22.0/bin/openclaw")


def _dry_run(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")


def _memory_dir() -> Path:
    """Directory for daily `YYYY-MM-DD.md` files (search index expects workspace memory by default)."""
    override = os.getenv("OPENCLAW_MEMORY_DIR") or os.getenv("OPENCLAW_DAILY_MEMORY_DIR")
    if override:
        return Path(override).expanduser()
    ws = os.getenv("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace"))
    return Path(ws).expanduser() / "memory"


def _daily_path() -> Path:
    day = datetime.now().strftime("%Y-%m-%d")
    return _memory_dir() / f"{day}.md"


class _JsonFileCache:
    """Same backing file as monitor CacheAdapter (`MONITOR_CACHE_JSON`)."""

    def __init__(self) -> None:
        self.path = Path(os.getenv("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            logger.warning("openclaw_memory cache save failed: %s", e)

    def get(self, namespace: str, key: str) -> Any:
        return self._load().get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any) -> None:
        data = self._load()
        data.setdefault(namespace, {})[key] = value
        self._save(data)


class OpenClawMemoryAdapter(RuntimeAdapter):
    """
    Adapter group: openclaw_memory
    Verbs: append_today, read_today, search
    """

    _SEARCH_CACHE_TTL_S = 90

    def __init__(self) -> None:
        self._cache = _JsonFileCache()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = _dry_run(context)

        if verb == "append_today":
            if len(args) < 1:
                raise AdapterError("append_today requires text: str")
            text = str(args[0])
            if dry:
                logger.info("[dry_run] openclaw_memory.append_today — no write")
                return 1
            path = _daily_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            line = f"- {iso} — {text}\n"
            day = path.stem
            if not path.exists():
                header = f"# Memory Log - {day}\n\n## AINL · OpenClaw bridge\n\n"
                path.write_text(header + line, encoding="utf-8")
            else:
                body = path.read_text(encoding="utf-8")
                if "## AINL · OpenClaw bridge" not in body:
                    body = body.rstrip() + "\n\n## AINL · OpenClaw bridge\n\n"
                body = body.rstrip() + "\n" + line
                path.write_text(body + "\n", encoding="utf-8")
            return 1

        if verb == "read_today":
            path = _daily_path()
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8")

        if verb == "search":
            if len(args) < 1:
                raise AdapterError("search requires query: str")
            query = str(args[0])
            ck = hashlib.sha256(query.encode("utf-8")).hexdigest()[:24]
            cached = self._cache.get("openclaw_memory_search", ck)
            if isinstance(cached, dict):
                ts = float(cached.get("ts", 0))
                if time.time() - ts < self._SEARCH_CACHE_TTL_S:
                    return cached.get("results", [])
            if dry:
                logger.info("[dry_run] openclaw_memory.search — no CLI")
                return []
            try:
                proc = subprocess.run(
                    [
                        OPENCLAW_BIN,
                        "memory",
                        "search",
                        "--query",
                        query,
                        "--max-results",
                        "20",
                        "--json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except FileNotFoundError:
                logger.warning("openclaw binary not found: %s", OPENCLAW_BIN)
                return []
            except subprocess.TimeoutExpired:
                logger.warning("openclaw memory search timed out")
                return []
            if proc.returncode != 0:
                logger.warning("memory search failed: %s", (proc.stderr or "")[:500])
                return []
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                logger.warning("memory search JSON error: %s", e)
                return []
            raw = data.get("results") if isinstance(data, dict) else None
            if not isinstance(raw, list):
                raw = []
            normalized: List[Dict[str, Any]] = []
            for r in raw:
                if isinstance(r, dict):
                    normalized.append(
                        {
                            "path": r.get("path"),
                            "snippet": r.get("snippet"),
                            "score": r.get("score"),
                            "startLine": r.get("startLine"),
                            "endLine": r.get("endLine"),
                            "source": r.get("source"),
                        }
                    )
            self._cache.set("openclaw_memory_search", ck, {"ts": time.time(), "results": normalized})
            return normalized

        raise AdapterError(f"openclaw_memory unknown target: {target}")
