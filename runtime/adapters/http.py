from __future__ import annotations

import http.client
import json
import math
import socket
import ssl
import time
from email.message import EmailMessage
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener, urlopen

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


_HOP_STRIP = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "x-amz-security-token",
    }
)


def _positive_finite(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise AdapterError(f"http {label} must be a positive finite number")
    return number


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, pin_ip: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._pin_ip = pin_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pin_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        pin_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._pin_ip = pin_ip

    def connect(self) -> None:
        raw = socket.create_connection((self._pin_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _headers_for_redirect(headers: Dict[str, str], previous_host: str, next_host: str) -> Dict[str, str]:
    """Drop credentials when a redirect leaves the host that was allowlisted."""
    if (previous_host or "").lower() == (next_host or "").lower():
        return dict(headers)
    return {key: value for key, value in headers.items() if key.lower() not in _HOP_STRIP}


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
        block_private: bool = True,
        allow_insecure_local: bool = False,
        https_only: bool = True,
        status_as_value: bool = True,
        max_redirects: int = 3,
        check_redirects: bool = True,
        allow_public: bool = False,
    ):
        self.default_timeout_s = _positive_finite(default_timeout_s, "timeout")
        self.max_response_bytes = int(max_response_bytes)
        if not math.isfinite(self.max_response_bytes) or self.max_response_bytes <= 0:
            raise AdapterError("http timeout and response cap must be positive")
        self.allow_hosts = set(allow_hosts or [])
        self.block_private = bool(block_private)
        self.allow_insecure_local = bool(allow_insecure_local)
        self.https_only = bool(https_only)
        self.status_as_value = bool(status_as_value)
        self.max_redirects = max(0, int(max_redirects))
        self.check_redirects = bool(check_redirects)
        self.allow_public = bool(allow_public)
        self.payment_profile = str(payment_profile or "none").strip().lower()
        if self.payment_profile not in {"none", "auto", "mpp", "x402"}:
            raise AdapterError("http adapter invalid payment_profile (use none|auto|mpp|x402)")
        # Reserved for facilitator / multi-hop flows; surfaced for CLI/runner parity today.
        self.max_payment_rounds = max(1, int(max_payment_rounds))

    def _payment_enabled(self) -> bool:
        return self.payment_profile in {"auto", "mpp", "x402"}

    def _validate_url(self, url: str) -> List[str]:
        """Return the addresses this request may connect to.

        An empty allowlist denies every public host unless ``allow_public``
        is set. That flag is off by default. It admits any public HTTPS host
        that already passed the private-address check. ``*`` and
        ``*.example.com`` stay exact names. Metadata, link-local, and private
        addresses stay closed when the host is admitted only by this flag.
        ``allow_insecure_local`` opens loopback and private addresses only
        for an exact allowlist entry, and metadata stays closed. The returned
        addresses were checked. The pinned reader connects to the first of them.
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise AdapterError("http adapter requires http/https url")
        if not parsed.netloc or not parsed.hostname:
            raise AdapterError("http adapter url missing host")
        if self.https_only and parsed.scheme != "https":
            raise AdapterError("http adapter requires https url")
        host = parsed.hostname.lower()
        allowed = {item.lower() for item in self.allow_hosts}
        exact = host in allowed
        if exact:
            pass
        elif self.allow_public:
            if parsed.scheme != "https":
                raise AdapterError("http host blocked by allowlist")
        elif self.allow_insecure_local and not allowed:
            from runtime.net_guard import host_is_blocked

            if not host_is_blocked(host):
                raise AdapterError("http host blocked by allowlist")
        else:
            raise AdapterError("http host blocked by allowlist")
        if not self.block_private:
            return []
        from runtime.net_guard import AddressRejected, check_fetch_url

        # Admitted by the public flag: HTTPS only, and private stays closed.
        # An exact allowlist entry keeps the adapter's own https and
        # allow_insecure_local settings. Metadata stays closed either way.
        admitted_by_public = self.allow_public and not exact
        try:
            return list(
                check_fetch_url(
                    url,
                    https_only=True if admitted_by_public else self.https_only,
                    allow_private=self.allow_insecure_local and not admitted_by_public,
                    resolve=True,
                )
            )
        except AddressRejected as exc:
            raise AdapterError(str(exc)) from exc

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
            "final_url": url,
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
        self._request_final_url = url
        if not self.check_redirects:
            return self._read_once(url, data=data, headers=headers, method=method, timeout_s=timeout_s)
        current = url
        hop_headers = dict(headers)
        hop_data = data
        hop_method = method
        for hop in range(self.max_redirects + 1):
            pins = self._validate_url(current)
            pin = pins[0] if pins else None
            try:
                return self._read_once(
                    current,
                    data=hop_data,
                    headers=hop_headers,
                    method=hop_method,
                    timeout_s=timeout_s,
                    follow=False,
                    pin_ip=pin,
                )
            except HTTPError as exc:
                code = int(getattr(exc, "code", 0) or 0)
                if code in {301, 302, 303, 307, 308} and hop < self.max_redirects:
                    loc = ""
                    hdrs = getattr(exc, "headers", None) or getattr(exc, "hdrs", None)
                    if hdrs is not None:
                        loc = str(hdrs.get("Location") or hdrs.get("location") or "")
                    if not loc:
                        self._request_final_url = current
                        raise
                    nxt = urljoin(current, loc)
                    previous = urlparse(current).hostname or ""
                    arriving = urlparse(nxt).hostname or ""
                    hop_headers = _headers_for_redirect(hop_headers, previous, arriving)
                    if code in {301, 302, 303}:
                        hop_data = None
                        hop_method = "GET"
                    current = nxt
                    self._request_final_url = current
                    continue
                self._request_final_url = current
                raise
        raise AdapterError("http redirect limit")

    def _read_once(
        self,
        url: str,
        *,
        data: Optional[bytes],
        headers: Dict[str, str],
        method: str,
        timeout_s: float,
        follow: bool = True,
        pin_ip: Optional[str] = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        self._request_final_url = url
        if pin_ip:
            return self._read_pinned(
                url,
                data=data,
                headers=headers,
                method=method,
                timeout_s=timeout_s,
                pin_ip=pin_ip,
            )
        req = Request(url=url, data=data, headers=headers, method=method)

        class _NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
                return None

        if follow:
            cm = urlopen(req, timeout=timeout_s, context=_default_ssl_context())
        else:
            opener = build_opener(_NoRedirect, HTTPSHandler(context=_default_ssl_context()))
            cm = opener.open(req, timeout=timeout_s)
        with cm as resp:
            status = int(getattr(resp, "status", 200))
            resp_headers = {k.lower(): v for k, v in dict(resp.headers).items()}
            body = resp.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise AdapterError("http response too large")
            return status, resp_headers, body

    def _read_pinned(
        self,
        url: str,
        *,
        data: Optional[bytes],
        headers: Dict[str, str],
        method: str,
        timeout_s: float,
        pin_ip: str,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """Connect to the address that was checked. SNI and Host stay the name.

        A graph-supplied Host header is dropped. The name from the URL is
        the only Host this socket will send.
        """
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        port = parsed.port or (443 if scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        clean = {key: value for key, value in headers.items() if key.lower() != "host"}
        if scheme == "https":
            conn: http.client.HTTPConnection = _PinnedHTTPSConnection(
                parsed.hostname or "",
                port,
                pin_ip,
                timeout_s,
                _default_ssl_context(),
            )
        else:
            conn = _PinnedHTTPConnection(parsed.hostname or "", port, pin_ip, timeout_s)
        try:
            conn.request(method, path, body=data, headers=clean)
            resp = conn.getresponse()
            status = int(resp.status)
            resp_headers = {key.lower(): value for key, value in resp.getheaders()}
            body = resp.read(self.max_response_bytes + 1)
        finally:
            conn.close()
        if len(body) > self.max_response_bytes:
            raise AdapterError("http response too large")
        if status >= 300:
            msg = EmailMessage()
            for key, value in resp_headers.items():
                msg[key] = value
            raise HTTPError(url, status, "http status", msg, BytesIO(body))
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

        if self.status_as_value:
            raw = _read_http_error_body(e)
            if len(raw) > self.max_response_bytes:
                raise AdapterError("http response too large")
            parsed_body = self._parse_response_body(hdrs_lc, raw)
            final = str(getattr(e, "url", "") or request_url or "")
            return {
                "ok": False,
                "status": status,
                "status_code": status,
                "error": None,
                "body": parsed_body,
                "headers": hdrs_lc,
                "url": request_url,
                "final_url": final or request_url,
            }
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
        timeout_s = _positive_finite(timeout_s, "timeout")

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
                envelope = self._success_envelope(
                    status=status,
                    parsed_body=parsed_body,
                    resp_headers=resp_headers,
                    url=url,
                    payment_meta=pay_meta,
                )
                envelope["final_url"] = getattr(self, "_request_final_url", url)
                return envelope
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
