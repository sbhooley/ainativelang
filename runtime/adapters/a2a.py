"""A2A (Agent-to-Agent) client adapter — aligned with ArmaraOS `openfang-runtime` `A2aClient`.

- discover: GET `{base}/.well-known/agent.json`
- send: JSON-RPC 2.0 `tasks/send` to the A2A endpoint URL
- get_task: JSON-RPC 2.0 `tasks/get` to the A2A endpoint URL

**Security (SSRF / redirects):** By default HTTP redirects are *not* followed. Optional
`strict_ssrf` resolves DNS and rejects hostnames that resolve to loopback/private/link-local
unless ``allow_insecure_local`` is set. See ``docs/integrations/A2A_ADAPTER.md``.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import time
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPHandler, HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from runtime.adapters.base import AdapterError, HttpAdapter

try:
    import certifi  # type: ignore

    def _default_ssl_context() -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())
except Exception:

    def _default_ssl_context() -> ssl.SSLContext:
        return ssl.create_default_context()


def _host_limited(host: str) -> bool:
    """True if the host is localhost, a loopback/private/link-local IP literal, or an IPv4-mapped private."""
    h = (host or "").strip()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if h.lower() in ("localhost", "ip6-localhost", "ip6-loopback"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            return True
    except ValueError:
        pass
    return False


def _is_ip_literal(host: str) -> bool:
    h = (host or "").strip()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False


def _a2a_url_guard(
    url: str,
    *,
    allow_hosts: Set[str],
    allow_insecure_local: bool,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AdapterError("a2a adapter requires http or https url")
    host = (parsed.hostname or "").strip()
    if not host:
        raise AdapterError("a2a url missing host")
    if not allow_insecure_local and _host_limited(host):
        raise AdapterError(
            "a2a: blocked private or local host; set allow_insecure_local to talk to same-host/lab peers"
        )
    if allow_hosts and host not in allow_hosts:
        raise AdapterError(f"a2a: host not in allowlist: {host!r}")


def _strict_resolve_url(
    url: str,
    *,
    allow_insecure_local: bool,
) -> None:
    """If hostname is not a literal IP, resolve via DNS; fail if any address is loopback/private/link-local
    and ``allow_insecure_local`` is false (mitigates some DNS-rebinding to RFC1918 cases for hostnames)."""
    host = (urlparse(url).hostname or "").strip()
    if not host:
        return
    if _is_ip_literal(host):
        return
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise AdapterError(f"a2a strict SSRF: DNS failed for {host!r}: {e}") from e
    for info in infos:
        sa = info[4]
        if not sa:
            continue
        ip_s = sa[0]
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            continue
        is_lim = bool(ip.is_loopback or ip.is_private or ip.is_link_local)
        if is_lim and not allow_insecure_local:
            raise AdapterError(
                f"a2a strict SSRF: {host!r} resolves to {ip_s!r} (non-public). "
                "set allow_insecure_local or do not use strict mode"
            )


def _a2a_url_full_check(
    url: str,
    *,
    allow_hosts: Set[str],
    allow_insecure_local: bool,
    strict_ssrf: bool,
) -> None:
    _a2a_url_guard(
        url,
        allow_hosts=allow_hosts,
        allow_insecure_local=allow_insecure_local,
    )
    if strict_ssrf:
        _strict_resolve_url(url, allow_insecure_local=allow_insecure_local)


def _user_agent() -> str:
    return "AINL/1.0 A2A"


def _read_json_or_text(resp_headers: Dict[str, str], body: bytes, max_bytes: int) -> Any:
    ctype = (resp_headers.get("content-type") or "").lower()
    if "application/json" in ctype and body:
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return body.decode("utf-8", errors="replace")
    return body.decode("utf-8", errors="replace") if body else None


def _opener_for(adapter: "A2aAdapter"):
    """Opener: no HTTP redirects by default, or redirect handler that re-validates each Location."""
    ctx = _default_ssl_context()
    https = HTTPSHandler(context=ctx)
    hhttp = HTTPHandler()
    if not adapter.follow_redirects:
        return build_opener(hhttp, https)
    a = adapter

    class _A2aRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            full = urljoin(req.get_full_url(), newurl)
            _a2a_url_full_check(
                full,
                allow_hosts=a.allow_hosts,
                allow_insecure_local=a.allow_insecure_local,
                strict_ssrf=a.strict_ssrf,
            )
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return build_opener(_A2aRedirect, hhttp, https)


def _urlopen_with_retries(
    req: Request,
    timeout_s: float,
    max_bytes: int,
    *,
    adapter: "A2aAdapter",
) -> Dict[str, Any]:
    max_attempts = 3
    base_backoff = 0.1
    attempt = 0
    opener = _opener_for(adapter)
    while attempt < max_attempts:
        try:
            with opener.open(req, timeout=timeout_s) as resp:
                status = int(getattr(resp, "status", 200))
                hmap = {k.lower(): v for k, v in dict(resp.headers).items()}
                raw = resp.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise AdapterError("a2a response too large")
                return {"status": status, "headers": hmap, "body": raw, "ok": 200 <= status < 300}
        except HTTPError as e:
            err_body = b""
            try:
                if e.fp is not None:
                    err_body = e.fp.read()[: max_bytes + 1]
            except Exception:
                pass
            status = getattr(e, "code", None)
            if status is not None and 500 <= status < 600 and attempt < max_attempts - 1:
                attempt += 1
                time.sleep(base_backoff * (2 ** (attempt - 1)))
                continue
            if err_body and len(err_body) <= max_bytes and status is not None:
                try:
                    hmap = {k.lower(): v for k, v in (dict(e.headers) if e.headers else {}).items()}
                    return {
                        "status": int(status),
                        "headers": hmap,
                        "body": err_body,
                        "ok": False,
                    }
                except Exception:
                    pass
            raise AdapterError(f"a2a http error: {e}") from e
        except (URLError, socket.timeout, TimeoutError) as e:
            if attempt < max_attempts - 1:
                attempt += 1
                time.sleep(base_backoff * (2 ** (attempt - 1)))
                continue
            raise AdapterError(f"a2a transport error: {e}") from e
    raise AdapterError("a2a: max retries exceeded")


def _from_env_allow_hosts() -> Set[str]:
    raw = (os.environ.get("AINL_A2A_ALLOW_HOSTS") or "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def a2a_from_env() -> "A2aAdapter":
    """Build adapter from env: AINL_A2A_*. See ``docs/integrations/A2A_ADAPTER.md``."""
    allow = _from_env_allow_hosts()
    lcl = _env_truthy("AINL_A2A_ALLOW_INSECURE_LOCAL")
    t_s = float((os.environ.get("AINL_A2A_TIMEOUT_S") or "30.0").strip() or 30.0)
    m_b = int((os.environ.get("AINL_A2A_MAX_BYTES") or "1000000").strip() or 1_000_000)
    strict = _env_truthy("AINL_A2A_STRICT_SSRF")
    follow = _env_truthy("AINL_A2A_FOLLOW_REDIRECTS")
    return A2aAdapter(
        allow_hosts=allow,
        allow_insecure_local=lcl,
        default_timeout_s=t_s,
        max_response_bytes=m_b,
        strict_ssrf=strict,
        follow_redirects=follow,
    )


class A2aAdapter(HttpAdapter):
    def __init__(
        self,
        *,
        allow_hosts: Optional[Iterable[str]] = None,
        allow_insecure_local: bool = False,
        default_timeout_s: float = 30.0,
        max_response_bytes: int = 1_000_000,
        strict_ssrf: bool = False,
        follow_redirects: bool = False,
    ):
        self.allow_hosts = {str(x).strip() for x in (allow_hosts or []) if str(x).strip()}
        self.allow_insecure_local = bool(allow_insecure_local)
        self.default_timeout_s = float(default_timeout_s)
        self.max_response_bytes = int(max_response_bytes)
        self.strict_ssrf = bool(strict_ssrf)
        self.follow_redirects = bool(follow_redirects)

    def _check_url(self, url: str) -> None:
        _a2a_url_full_check(
            url,
            allow_hosts=self.allow_hosts,
            allow_insecure_local=self.allow_insecure_local,
            strict_ssrf=self.strict_ssrf,
        )

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t = (target or "").strip().lower()
        if t in ("get", "get_task", "task_get"):
            t = "get_task"
        if t == "discover":
            if not args:
                raise AdapterError("a2a discover requires base url")
            base = str(args[0]).rstrip("/")
            self._check_url(base)
            return self._do_discover(base)
        if t == "send":
            if len(args) < 2:
                raise AdapterError("a2a send requires a2a_endpoint_url and message")
            u = str(args[0])
            self._check_url(u)
            message = str(args[1])
            session: Optional[str] = None
            if len(args) > 2 and args[2] is not None and str(args[2]).strip() != "":
                session = str(args[2])
            timeout = float(args[3]) if len(args) > 3 else self.default_timeout_s
            return self._do_jsonrpc(
                u,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "parts": [{"type": "text", "text": message}],
                        },
                        "sessionId": session,
                    },
                },
                timeout,
            )
        if t == "get_task":
            if len(args) < 2:
                raise AdapterError("a2a get_task requires a2a_endpoint_url and task_id")
            u = str(args[0])
            self._check_url(u)
            task_id = str(args[1])
            timeout = float(args[2]) if len(args) > 2 else self.default_timeout_s
            return self._do_jsonrpc(
                u,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/get",
                    "params": {"id": task_id},
                },
                timeout,
            )
        raise AdapterError(f"unknown a2a target: {target!r} (use discover, send, get_task)")

    def _do_discover(self, base: str) -> Any:
        url = f"{base}/.well-known/agent.json"
        self._check_url(url)
        req = Request(
            url=url,
            headers={"User-Agent": _user_agent(), "Accept": "application/json"},
            method="GET",
        )
        r = _urlopen_with_retries(req, self.default_timeout_s, self.max_response_bytes, adapter=self)
        st = r["status"]
        body = _read_json_or_text(r["headers"], r["body"], self.max_response_bytes)
        if not (200 <= st < 300):
            raise AdapterError(f"a2a discover failed: HTTP {st}")
        if isinstance(body, (dict, list)):
            return body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except Exception as e:
                raise AdapterError(f"a2a discover: invalid json: {e}") from e
        return body

    def _do_jsonrpc(self, url: str, payload: Dict[str, Any], timeout_s: float) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            url=url,
            data=data,
            headers={
                "User-Agent": _user_agent(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        r = _urlopen_with_retries(req, timeout_s, self.max_response_bytes, adapter=self)
        st = r["status"]
        raw = r["body"]
        if len(raw) > self.max_response_bytes:
            raise AdapterError("a2a response too large")
        if not (200 <= st < 300):
            try:
                j = json.loads(raw.decode("utf-8")) if raw else None
            except Exception:
                j = None
            if isinstance(j, dict) and "error" in j:
                return j
            raise AdapterError(f"a2a request failed: HTTP {st} {raw[:500]!r}")

        try:
            body: Any = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as e:
            raise AdapterError(f"a2a: invalid json response: {e}") from e
        if isinstance(body, dict):
            if body.get("error") is not None:
                raise AdapterError(f"a2a json-rpc error: {body.get('error')!r}")
            if "result" in body:
                return body["result"]
        return body
