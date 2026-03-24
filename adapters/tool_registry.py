# adapters/tool_registry.py
"""
Local JSON file tool catalog (list / get / register / discover).

Enable: ``--enable-adapter tool_registry`` on the CLI host.

AINL (examples):
  R tool_registry list ->tools
  R tool_registry discover ->envelope
  R tool_registry get name ->row
  R tool_registry register name description [schema_json] ->ok

Env:
  AINL_TOOL_REGISTRY_PATH — registry file (default: .ainl_tool_registry.json in cwd)

Verbs (target, case-insensitive): LIST, GET, REGISTER, DISCOVER
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter


class ToolRegistryAdapter(RuntimeAdapter):
    def __init__(self, path: Optional[str] = None):
        raw = (path or os.environ.get("AINL_TOOL_REGISTRY_PATH") or "").strip()
        self.path = Path(raw) if raw else Path.cwd() / ".ainl_tool_registry.json"
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._tools = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            tools = data.get("tools") if isinstance(data, dict) else None
            if isinstance(tools, dict):
                self._tools = {str(k): dict(v) if isinstance(v, dict) else {} for k, v in tools.items()}
            else:
                self._tools = {}
        except Exception as e:
            raise AdapterError(f"tool_registry: cannot read {self.path}: {e}") from e

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "updated_at": time.time(), "tools": self._tools}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().upper()
        if verb == "LIST":
            return sorted(self._tools.values(), key=lambda x: str(x.get("name", "")))
        if verb == "DISCOVER":
            return {"tools": sorted(self._tools.values(), key=lambda x: str(x.get("name", "")))}
        if verb == "GET":
            if not args:
                raise AdapterError("tool_registry.GET requires name")
            name = str(args[0])
            if name not in self._tools:
                return {"found": False, "tool": None}
            return {"found": True, "tool": self._tools[name]}
        if verb == "REGISTER":
            if len(args) < 2:
                raise AdapterError("tool_registry.REGISTER requires name description [schema_json]")
            name = str(args[0])
            desc = str(args[1]) if len(args) > 1 else ""
            schema: Dict[str, Any] = {}
            if len(args) >= 3 and args[2] is not None:
                try:
                    schema = json.loads(str(args[2]))
                    if not isinstance(schema, dict):
                        raise ValueError("schema must be a JSON object")
                except Exception as e:
                    raise AdapterError(f"tool_registry.REGISTER invalid schema JSON: {e}") from e
            self._tools[name] = {
                "name": name,
                "description": desc,
                "schema": schema,
                "registered_at": time.time(),
            }
            self._save()
            return {"ok": True, "name": name}
        raise AdapterError(f"tool_registry unsupported verb: {target!r}")
