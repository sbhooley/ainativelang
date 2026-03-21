import json
import os
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from urllib.error import HTTPError, URLError

from runtime.adapters.base import AdapterError
from runtime.adapters.http import SimpleHttpAdapter


class _Handler(BaseHTTPRequestHandler):
    calls = 0

    def do_GET(self):
        _Handler.calls += 1
        if self.path == "/slow":
            time.sleep(0.2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"calls": _Handler.calls}).encode("utf-8"))

    def do_POST(self):
        _Handler.calls += 1
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"body": body, "calls": _Handler.calls}).encode("utf-8"))

    def log_message(self, fmt, *args):
        return


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _start_server():
    _Handler.calls = 0
    srv = _ThreadedHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv


def test_http_adapter_get_json_and_idempotent_calls():
    srv = _start_server()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        adp = SimpleHttpAdapter(default_timeout_s=1.0)
        url = f"{base}/ok"
        r1 = adp.call("get", [url], {})
        r2 = adp.call("get", [url], {})
        # Legacy fields still behave as before.
        assert r1["status"] == 200 and r2["status"] == 200
        assert r1["body"]["calls"] == 1
        assert r2["body"]["calls"] == 2
        # New success envelope fields are populated and consistent.
        assert r1["ok"] is True and r2["ok"] is True
        assert r1["status_code"] == r1["status"]
        assert r2["status_code"] == r2["status"]
        assert r1["error"] is None and r2["error"] is None
        assert r1["url"] == url and r2["url"] == url
    finally:
        srv.shutdown()


def test_http_adapter_post_json_body_roundtrip():
    srv = _start_server()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        adp = SimpleHttpAdapter(default_timeout_s=1.0)
        url = f"{base}/post"
        r = adp.call("post", [url, {"x": 1}], {})
        # Legacy fields.
        assert r["status"] == 200
        assert '"x": 1' in r["body"]["body"]
        # Success envelope.
        assert r["ok"] is True
        assert r["status_code"] == r["status"]
        assert r["error"] is None
        assert r["url"] == url
    finally:
        srv.shutdown()


def test_http_adapter_input_validation_and_allowlist():
    adp = SimpleHttpAdapter(allow_hosts=["example.com"])
    try:
        adp.call("get", ["file:///tmp/x"], {})
        assert False, "expected scheme validation error"
    except Exception as e:
        assert isinstance(e, AdapterError)
    try:
        adp.call("get", ["https://not-allowed.local/x"], {})
        assert False, "expected allowlist error"
    except Exception as e:
        assert isinstance(e, AdapterError)


def test_http_adapter_timeout_maps_to_adapter_error():
    srv = _start_server()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        adp = SimpleHttpAdapter(default_timeout_s=0.01)
        try:
            adp.call("get", [f"{base}/slow"], {})
            assert False, "expected timeout"
        except Exception as e:
            assert isinstance(e, AdapterError)
            assert "transport error" in str(e)
    finally:
        srv.shutdown()


def test_http_adapter_retries_on_transport_error(monkeypatch):
    calls = {"n": 0}

    class _FakeResp:
        def __init__(self):
            self.status = 200
            self.headers = {}

        def read(self, n: int) -> bytes:
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise URLError("temporary")
        return _FakeResp()

    monkeypatch.setattr("runtime.adapters.http.urlopen", _fake_urlopen)
    monkeypatch.setattr("runtime.adapters.http.time.sleep", lambda s: None)

    adp = SimpleHttpAdapter(default_timeout_s=1.0)
    # Host allowlist is empty by default; external URL is fine for this fake.
    res = adp.call("get", ["https://example.com"], {})
    assert res["ok"] is True
    assert calls["n"] == 2


def test_http_adapter_retries_and_eventually_fails(monkeypatch):
    calls = {"n": 0}

    def _always_fail(req, timeout=None, **kwargs):
        calls["n"] += 1
        raise URLError("temporary")

    monkeypatch.setattr("runtime.adapters.http.urlopen", _always_fail)
    monkeypatch.setattr("runtime.adapters.http.time.sleep", lambda s: None)

    adp = SimpleHttpAdapter(default_timeout_s=1.0)
    try:
        adp.call("get", ["https://example.com"], {})
        assert False, "expected transport error after retries"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "transport error" in str(e)
        # 3 attempts total (1 initial + 2 retries).
        assert calls["n"] == 3


def test_http_adapter_does_not_retry_on_4xx(monkeypatch):
    calls = {"n": 0}

    def _fail_400(req, timeout=None, **kwargs):
        calls["n"] += 1
        raise HTTPError("https://example.com", 400, "bad request", {}, None)

    monkeypatch.setattr("runtime.adapters.http.urlopen", _fail_400)
    monkeypatch.setattr("runtime.adapters.http.time.sleep", lambda s: None)

    adp = SimpleHttpAdapter(default_timeout_s=1.0)
    try:
        adp.call("get", ["https://example.com"], {})
        assert False, "expected 4xx error"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "status error" in str(e)
        # Only one attempt for 4xx.
        assert calls["n"] == 1


def test_http_adapter_retries_on_5xx_then_fails(monkeypatch):
    calls = {"n": 0}

    def _fail_500(req, timeout=None, **kwargs):
        calls["n"] += 1
        raise HTTPError("https://example.com", 500, "server error", {}, None)

    monkeypatch.setattr("runtime.adapters.http.urlopen", _fail_500)
    monkeypatch.setattr("runtime.adapters.http.time.sleep", lambda s: None)

    adp = SimpleHttpAdapter(default_timeout_s=1.0)
    try:
        adp.call("get", ["https://example.com"], {})
        assert False, "expected 5xx error after retries"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "status error" in str(e)
        # 3 attempts total for retryable 5xx.
        assert calls["n"] == 3
