"""`ext` adapter: echo-compatible plus optional subprocess execution.

Verbs (case-insensitive):
  echo, op, G, etc. — return ``args[0]`` if present else ``target`` (legacy tests)
  EXEC, RUN — subprocess (requires ``AINL_EXT_ALLOW_EXEC=1``)

Env:
  AINL_EXT_ALLOW_EXEC — must be truthy for EXEC/RUN
  AINL_EXT_EXEC_TIMEOUT — seconds (default 120)
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List

from runtime.adapters.base import AdapterError, RuntimeAdapter


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


class StdExtAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t = (target or "").strip().lower()
        if t in ("exec", "run"):
            if not _truthy(os.environ.get("AINL_EXT_ALLOW_EXEC")):
                raise AdapterError("ext.EXEC/RUN disabled; set AINL_EXT_ALLOW_EXEC=1")
            if not args:
                raise AdapterError("ext.EXEC requires argv list")
            argv = [str(a) for a in args]
            timeout = float(os.environ.get("AINL_EXT_EXEC_TIMEOUT", "120"))
            try:
                cp = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as e:
                raise AdapterError(f"ext.EXEC timeout after {timeout}s: {e}") from e
            except FileNotFoundError as e:
                raise AdapterError(f"ext.EXEC executable not found: {e}") from e
            return {
                "exit_code": cp.returncode,
                "stdout": cp.stdout,
                "stderr": cp.stderr,
            }
        return args[0] if args else target
