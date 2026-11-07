"""
Phase 2: run examples/integrations/executor_bridge_min.ainl against an in-process HTTP mock.

No live network; no manual scripts/mock_executor_bridge.py required for CI.
"""
from __future__ import annotations

import json
import os
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterRegistry
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.engine import RuntimeEngine

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "integrations" / "executor_bridge_min.ainl"
# URL baked into the example (must match for str.replace in tests).
PLACEHOLDER_URL = "http://127.0.0.1:17300/v1/execute"


class _BridgeHandler(BaseHTTPRequestHandler):
    status_code = 200
    last_body: Optional[Dict[str, Any]] = None

    def do_POST(self) -> None:
        if self.path != "/v1/execute":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_error(400, "bad json")
            return
        _BridgeHandler.last_body = body
        out = {
            "accepted": True,
            "executor": body.get("executor"),
            "run_id": body.get("run_id"),
            "echo_payload": body.get("payload"),
        }
        data = json.dumps(out).encode("utf-8")
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        return


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _start_bridge_server(*, status_code: int = 200):
    _BridgeHandler.status_code = status_code
    _BridgeHandler.last_body = None
    srv = _ThreadedHTTPServer(("127.0.0.1", 0), _BridgeHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv


def _registry() -> AdapterRegistry:
    reg = AdapterRegistry(allowed=["core", "http"])
    reg.register("core", CoreBuiltinAdapter())
    reg.register(
        "http",
        SimpleHttpAdapter(
            default_timeout_s=5.0,
            allow_hosts=["127.0.0.1"],
            https_only=False,
            allow_insecure_local=True,
            block_private=False,
            check_redirects=False,
            status_as_value=False,
        ),
    )
    return reg


def _program_for_port(port: int) -> str:
    src = EXAMPLE.read_text(encoding="utf-8")
    url = f"http://127.0.0.1:{port}/v1/execute"
    assert PLACEHOLDER_URL in src, f"example must contain {PLACEHOLDER_URL!r} for test substitution"
    return src.replace(PLACEHOLDER_URL, url, 1)


def test_executor_bridge_example_200_returns_bridge_ok():
    assert EXAMPLE.is_file(), f"missing {EXAMPLE}"
    srv = _start_bridge_server(status_code=200)
    try:
        code = _program_for_port(srv.server_port)
        eng = RuntimeEngine.from_code(code, strict=False, adapters=_registry())
        out = eng.run_label(eng.default_entry_label(), frame={})
        assert out == "bridge_ok"
    finally:
        srv.shutdown()


def test_executor_bridge_example_posts_contract_envelope():
    """Server records JSON body; assert EXTERNAL_EXECUTOR_BRIDGE request fields."""
    srv = _start_bridge_server(status_code=200)
    try:
        code = _program_for_port(srv.server_port)
        eng = RuntimeEngine.from_code(code, strict=False, adapters=_registry())
        eng.run_label(eng.default_entry_label(), frame={})
        body = _BridgeHandler.last_body
        assert body is not None
        assert body.get("run_id") == "example-run-001"
        assert body.get("step_id") == "L0"
        assert body.get("node_id") == "n_bridge"
        assert body.get("executor") == "demo.echo"
        assert body.get("payload") == {"hello": "world"}
        assert body.get("timeout_s") == 30
    finally:
        srv.shutdown()
