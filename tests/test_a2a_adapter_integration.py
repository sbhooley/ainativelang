"""
Integration: local HTTP server (127.0.0.1) + real a2a discover (no mock of _urlopen_with_retries).
Skips if binding fails (e.g. sandbox).
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from runtime.adapters.a2a import A2aAdapter


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/agent.json":
            host, port = self.server.server_address[:2]
            body = {
                "name": "test-agent",
                "url": f"http://{host}:{port}/a2a",
                "version": "0.0.1",
                "capabilities": {
                    "streaming": True,
                    "pushNotifications": False,
                    "stateTransitionHistory": True,
                },
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
            }
            raw = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.send_error(404)

    def log_message(self, *args, **kwargs):
        pass


class TestA2ALocalServer(unittest.TestCase):
    def test_discover_against_threaded_localhost_server(self):
        try:
            httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        except OSError:
            self.skipTest("Cannot bind 127.0.0.1 for integration test")
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            base = f"http://127.0.0.1:{port}"
            a = A2aAdapter(allow_hosts={"127.0.0.1"}, allow_insecure_local=True, default_timeout_s=5.0)
            out = a.call("discover", [base], {})
            self.assertEqual(out.get("name"), "test-agent")
        finally:
            httpd.shutdown()
            httpd.server_close()
            t.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
