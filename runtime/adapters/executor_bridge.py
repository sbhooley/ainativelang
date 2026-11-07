"""Optional HTTP executor bridge: map logical executor ids to URLs (Phase 3 EXTERNAL_EXECUTOR_BRIDGE)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from runtime.adapters.base import AdapterError, RuntimeAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.net_guard import host_is_blocked


class ExecutorBridgeAdapter(RuntimeAdapter):
    """
    Resolve `R bridge.Post <executor_key> <body_var> ->resp` by looking up <executor_key>
    in a server-provided endpoint table, then POST JSON via SimpleHttpAdapter.

    Not registered unless the host enables it (CLI `--enable-adapter bridge`, runner config).
    """

    def __init__(
        self,
        endpoints: Dict[str, str],
        *,
        default_timeout_s: float = 30.0,
        max_response_bytes: int = 1_000_000,
        allow_hosts: Optional[Iterable[str]] = None,
    ):
        if not endpoints:
            raise AdapterError("ExecutorBridgeAdapter requires non-empty endpoints mapping")
        self._endpoints = {str(k).strip(): str(v).strip() for k, v in endpoints.items() if str(k).strip() and str(v).strip()}
        if not self._endpoints:
            raise AdapterError("ExecutorBridgeAdapter endpoints mapping is empty after normalization")
        hosts = [str(item) for item in allow_hosts] if allow_hosts else []
        https_only = True
        insecure = False
        if not hosts:
            for endpoint in self._endpoints.values():
                parsed = urlparse(endpoint)
                if parsed.hostname:
                    hosts.append(parsed.hostname)
                if parsed.scheme != "https":
                    https_only = False
                if parsed.hostname and host_is_blocked(parsed.hostname):
                    insecure = True
        self._http = SimpleHttpAdapter(
            default_timeout_s=float(default_timeout_s),
            max_response_bytes=int(max_response_bytes),
            allow_hosts=hosts,
            https_only=https_only,
            allow_insecure_local=insecure,
            block_private=True,
            check_redirects=True,
            status_as_value=True,
        )

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        method = str(target or "").strip().upper()
        if method != "POST":
            raise AdapterError(f"bridge adapter unsupported verb: {target!r} (only Post)")
        if len(args) < 2:
            raise AdapterError("bridge.Post requires executor_key and json body")
        key = str(args[0]).strip()
        body = args[1]
        url = self._endpoints.get(key)
        if not url:
            raise AdapterError(f"bridge: unknown executor key: {key!r}")
        return self._http.call("post", [url, body], context)
