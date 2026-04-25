from __future__ import annotations

import json
import socket
import ssl
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from runtime.adapters.base import AdapterError, HttpAdapter
from runtime.adapters.http_machine_payments import (
    build_payment_challenge_envelope,
    merge_frame_payment_headers,
    normalize_header_dict,
    resolve_payment_profile,
)

# Build a default SSL context that uses certifi's CA bundle when available.
# This fixes macOS environments where the system cert store isn't linked.
def _default_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _headers_from_http_message(msg: Any) -> Dict[str, str]:
    """Normalize any mapping-like HTTP headers to a plain ``dict``."""
    if msg is None:
        return {}
    try:
        return {str(k): str(v) for k, v in dict(msg).items()}
    except Exception:
        return {}


def _read_http_error_body(err: HTTPError) -> bytes:
    try:
        data = err.read()
        return data if isinstance(data, (bytes, bytearray)) else bytes(data or b"")
    except Exception:
        return b""


class SimpleHttpAdapter(HttpAdapter):
    def __init__(
        self,
        *,
        default_timeout_s: float = 5.0,
        max_response_bytes: int = 1_000_000,
        allow_hosts: Optional[Iterable[str]] = None,
        payment_profile: str = "none",
        max_payment_rounds: int = 2,
    ):
        self.default_timeout_s = float(default_timeout_s)
        self.max_response_bytes = int(max_response_bytes)
        self.allow_hosts = set(allow_hosts or [])
        self.payment_profile = str(payment_profile or "none").strip().lower()
        if self.payment_profile not in {"none", "auto", "mpp", "x402"}:
            raise AdapterError("http adapter invalid payment_profile (use none|auto|mpp|x402)")
        # Reserved for facilitator / multi-hop flows; surfaced for CLI/runner parity today.
        self.max_payment_rounds = max(1, int(max_payment_rounds))

    def _payment_enabled(self) -> bool:
        return self.payment_profile in {"auto", "mpp", "x402"}

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise AdapterError("http adapter requires http/https url")
        if not parsed.netloc:
            raise AdapterError("http adapter url missing host")
        if self.allow_hosts and parsed.hostname not in self.allow_hosts:
            raise AdapterError(f"http host blocked by allowlist: {parsed.hostname}")

    def _parse_response_body(self, headers: Dict[str, str], body: bytes) -> Any:
        ctype = (headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return body.decode("utf-8", errors="replace")
        return body.decode("utf-8", errors="replace")

    def _success_envelope(
        self,
        *,
        status: int,
        parsed_body: Any,
        resp_headers: Dict[str, str],
        url: str,
        payment_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": 200 <= int(status) < 300,
            "status": int(status),
            "status_code": int(status),
            "error": None,
            "body": parsed_body,
            "headers": resp_headers,
            "url": url,
        }
        if payment_meta:
            out["payment"] = payment_meta
        return out

    def _perform_request(
        self,
        *,
        method: str,
        url: str,
        data: Optional[bytes],
        headers: Dict[str, str],
        timeout_s: float,
    ) -> Tuple[int, Dict[str, str], bytes]:
        req = Request(url=url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=timeout_s, context=_default_ssl_context()) as resp:
            status = int(getattr(resp, "status", 200))
            resp_headers = {k.lower(): v for k, v in dict(resp.headers).items()}
            body = resp.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise AdapterError("http response too large")
            return status, resp_headers, body

    def _payment_success_meta(self, resp_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if not self._payment_enabled():
            return None
        pr = resp_headers.get("payment-response")
        if pr:
            return {"profile": "x402", "payment_response_header": str(pr)}
        rcpt = resp_headers.get("payment-receipt")
        if rcpt:
            return {"profile": "mpp", "payment_receipt_header": str(rcpt)}
        return None

    def _handle_http_error(self, *, e: HTTPError, transport_attempt: int, request_url: str) -> Optional[Dict[str, Any]]:
        """Return a structured envelope for handled errors, or ``None`` to fall through."""
        status = int(getattr(e, "code", 0) or 0)
        hdrs_orig = _headers_from_http_message(getattr(e, "hdrs", None))
        hdrs_lc = normalize_header_dict(hdrs_orig)

        if status == 402 and self._payment_enabled():
            raw = _read_http_error_body(e)
            if len(raw) > self.max_response_bytes:
                raise AdapterError("http 402 response too large")
            parsed_body = self._parse_response_body(hdrs_lc, raw)
            prof = resolve_payment_profile(self.payment_profile, hdrs_lc)
            if not prof:
                prof = "unknown"
            pay = build_payment_challenge_envelope(
                profile=str(prof),
                headers_lc=hdrs_lc,
                headers_orig=hdrs_orig,
                body=parsed_body,
                url=str(getattr(e, "url", "") or request_url or ""),
            )
            return {
                "ok": False,
                "status": status,
                "status_code": status,
                "error": "payment_required",
                "body": parsed_body,
                "headers": hdrs_lc,
                "url": str(getattr(e, "url", "") or request_url or ""),
                "payment": pay,
            }

        if status and 500 <= status < 600 and transport_attempt < 2:
            return {"__retry_transport__": True}

        raise AdapterError(f"http status error: {e.code}") from e

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        method = str(target or "").strip().upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise AdapterError(f"unsupported http method: {method}")
        if not args:
            raise AdapterError("http adapter missing url argument")

        url = str(args[0])
        self._validate_url(url)

        body_obj: Any = None
        headers: Dict[str, str] = {}
        timeout_s: float = self.default_timeout_s

        if method in {"POST", "PUT", "PATCH"}:
            body_obj = args[1] if len(args) > 1 else None
            if len(args) > 2 and isinstance(args[2], dict):
                headers = {str(k): str(v) for k, v in args[2].items()}
            if len(args) > 3:
                timeout_s = float(args[3])
        else:
            if len(args) > 1 and isinstance(args[1], dict):
                headers = {str(k): str(v) for k, v in args[1].items()}
            if len(args) > 2:
                timeout_s = float(args[2])

        data: Optional[bytes] = None
        if body_obj is not None and method in {"POST", "PUT", "PATCH"}:
            if isinstance(body_obj, (dict, list)):
                data = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body_obj, bytes):
                data = body_obj
            else:
                data = str(body_obj).encode("utf-8")
                headers.setdefault("Content-Type", "text/plain; charset=utf-8")

        merged = merge_frame_payment_headers(headers, context)

        max_transport_attempts = 3
        base_backoff_s = 0.1
        transport_attempt = 0

        while transport_attempt < max_transport_attempts:
            try:
                status, resp_headers, body = self._perform_request(
                    method=method,
                    url=url,
                    data=data,
                    headers=merged,
                    timeout_s=timeout_s,
                )
                parsed_body = self._parse_response_body(resp_headers, body)
                pay_meta = self._payment_success_meta(resp_headers)
                return self._success_envelope(
                    status=status,
                    parsed_body=parsed_body,
                    resp_headers=resp_headers,
                    url=url,
                    payment_meta=pay_meta,
                )
            except HTTPError as e:
                handled = self._handle_http_error(
                    e=e, transport_attempt=transport_attempt, request_url=url
                )
                if isinstance(handled, dict) and handled.get("__retry_transport__"):
                    transport_attempt += 1
                    time.sleep(base_backoff_s * (2 ** (transport_attempt - 1)))
                    continue
                if isinstance(handled, dict):
                    return handled
                raise
            except (URLError, socket.timeout, TimeoutError) as ex:
                if transport_attempt < max_transport_attempts - 1:
                    transport_attempt += 1
                    time.sleep(base_backoff_s * (2 ** (transport_attempt - 1)))
                    continue
                raise AdapterError(f"http transport error: {ex}") from ex

        raise AdapterError("http internal error: transport loop exhausted")
