from __future__ import annotations

import hashlib
import json
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class SandboxClient:
    """Tiny optional sandbox/AVM connectivity shim with graceful fallback."""

    def __init__(self, connected: bool, provider: str, endpoint: str):
        self.connected = bool(connected)
        self.provider = provider
        self.endpoint = endpoint
        self.session_id = str(uuid.uuid4()) if connected else ""
        self._prev_hash = ""

    @classmethod
    def try_connect(
        cls,
        *,
        logger: Optional[Callable[[str], None]] = None,
        timeout_s: float = 0.2,
    ) -> "SandboxClient":
        def _log(msg: str) -> None:
            if logger is not None:
                logger(msg)

        avm_sock = os.environ.get("AINL_AVM_SOCKET", "").strip() or str(Path.home() / ".hyperspace" / "avmd.sock")
        generic_host = os.environ.get("AINL_SANDBOX_HOST", "").strip() or "127.0.0.1"
        generic_port = int(os.environ.get("AINL_SANDBOX_PORT", "7878"))
        avm_host = os.environ.get("AINL_AVM_HOST", "").strip() or generic_host
        avm_port = int(os.environ.get("AINL_AVM_PORT", "7811"))

        try:
            if Path(avm_sock).exists():
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout_s)
                    sock.connect(avm_sock)
                _log(f"AINL sandbox shim connected (avm:{avm_sock}).")
                return cls(True, "avm", avm_sock)
        except Exception:
            pass

        try:
            with socket.create_connection((avm_host, avm_port), timeout=timeout_s):
                pass
            _log(f"AINL sandbox shim connected (avm:{avm_host}:{avm_port}).")
            return cls(True, "avm", f"{avm_host}:{avm_port}")
        except Exception:
            pass

        try:
            with socket.create_connection((generic_host, generic_port), timeout=timeout_s):
                pass
            _log(f"AINL sandbox shim connected (general:{generic_host}:{generic_port}).")
            return cls(True, "general", f"{generic_host}:{generic_port}")
        except Exception:
            _log("AINL sandbox shim not connected; continuing without sandbox runtime.")
            return cls(False, "none", "unavailable")

    def event_hash(self, event: Dict[str, Any]) -> Optional[str]:
        if not self.connected:
            return None
        payload = {"prev": self._prev_hash, "event": event, "provider": self.provider}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        self._prev_hash = digest
        return digest

    def trajectory_metadata(self) -> Dict[str, Any]:
        if not self.connected:
            return {}
        return {
            "sandbox_session_id": self.session_id,
            "sandbox_provider": self.provider,
            "isolation_hash": self._prev_hash or None,
        }
