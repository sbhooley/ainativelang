import json
import socket
import unittest
from unittest.mock import patch

from runtime.adapters.base import AdapterError
from runtime.adapters.a2a import A2aAdapter, _host_limited


class TestHostLimited(unittest.TestCase):
    def test_localhost_name(self):
        self.assertTrue(_host_limited("localhost"))

    def test_public_name(self):
        self.assertFalse(_host_limited("a.example.com"))

    def test_loopback_ip(self):
        self.assertTrue(_host_limited("127.0.0.1"))


class TestA2AUrlGuardBehavior(unittest.TestCase):
    def test_rejects_127_without_insecure(self):
        a = A2aAdapter(allow_hosts={"127.0.0.1"}, allow_insecure_local=False)
        with self.assertRaises(AdapterError):
            a.call("discover", ["http://127.0.0.1:50051"], {})

    def test_allows_127_with_insecure(self):
        card = {
            "name": "t",
            "url": "http://127.0.0.1:50051/a2a",
            "version": "1",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "skills": [],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }
        a = A2aAdapter(allow_hosts={"127.0.0.1"}, allow_insecure_local=True)
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(card).encode("utf-8"),
            }
            out = a.call("discover", ["http://127.0.0.1:50051"], {})
            self.assertIn("name", out)

    def test_public_host_with_allowlist(self):
        card = {
            "name": "p",
            "url": "https://a.example.com/a2a",
            "version": "1",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "skills": [],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=False)
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(card).encode("utf-8"),
            }
            out = a.call("discover", ["https://a.example.com"], {})
            self.assertEqual(out["name"], "p")

    def test_rejects_host_not_in_allowlist(self):
        a = A2aAdapter(allow_hosts={"b.example.com"}, allow_insecure_local=True)
        with self.assertRaises(AdapterError):
            a.call("discover", ["https://a.example.com"], {})


class TestA2AStrictResolve(unittest.TestCase):
    def test_strict_rejects_host_resolving_to_loopback(self):
        a = A2aAdapter(allow_hosts={"trap.example.com"}, allow_insecure_local=False, strict_ssrf=True)
        with patch("runtime.adapters.a2a.socket.getaddrinfo") as gi:
            gi.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
            ]
            with self.assertRaises(AdapterError) as e:
                a._check_url("https://trap.example.com/")
            self.assertIn("strict", str(e.exception).lower())

    def test_strict_allows_public_resolve(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=False, strict_ssrf=True)
        with patch("runtime.adapters.a2a.socket.getaddrinfo") as gi:
            gi.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443)),
            ]
            with patch("runtime.adapters.a2a._urlopen_with_retries") as uo:
                uo.return_value = {
                    "status": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "name": "p",
                            "url": "https://a.example.com/a2a",
                            "version": "1",
                            "capabilities": {
                                "streaming": True,
                                "pushNotifications": False,
                                "stateTransitionHistory": True,
                            },
                            "skills": [],
                            "defaultInputModes": ["text"],
                            "defaultOutputModes": ["text"],
                        }
                    ).encode("utf-8"),
                }
                a.call("discover", ["https://a.example.com"], {})
        gi.assert_called()

    def test_no_strict_skips_getaddrinfo(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=True, strict_ssrf=False)
        with patch("runtime.adapters.a2a.socket.getaddrinfo") as gi:
            with patch("runtime.adapters.a2a._urlopen_with_retries") as uo:
                uo.return_value = {
                    "status": 200,
                    "headers": {"content-type": "application/json"},
                    "body": b"{}",
                }
                a.call("discover", ["https://a.example.com"], {})
        gi.assert_not_called()


class TestA2AJsonRpc(unittest.TestCase):
    def test_send_returns_result(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=True)
        body = {"jsonrpc": "2.0", "id": 1, "result": {"id": "t1", "status": "completed"}}
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(body).encode("utf-8"),
            }
            r = a.call("send", ["https://a.example.com/a2a", "hi"], {})
            self.assertEqual(r, {"id": "t1", "status": "completed"})

    def test_jsonrpc_error_raises(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=True)
        body = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "nope"}}
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(body).encode("utf-8"),
            }
            with self.assertRaises(AdapterError) as e:
                a.call("send", ["https://a.example.com/a2a", "hi"], {})
            self.assertIn("json-rpc", str(e.exception).lower())

    def test_get_task(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=True)
        body = {"jsonrpc": "2.0", "id": 1, "result": {"id": "t1"}}
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(body).encode("utf-8"),
            }
            r = a.call("get_task", ["https://a.example.com/a2a", "t1"], {})
            self.assertEqual(r["id"], "t1")

    def test_get_alias(self):
        a = A2aAdapter(allow_hosts={"a.example.com"}, allow_insecure_local=True)
        body = {"jsonrpc": "2.0", "id": 1, "result": {"id": "t2"}}
        with patch("runtime.adapters.a2a._urlopen_with_retries") as u:
            u.return_value = {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(body).encode("utf-8"),
            }
            r = a.call("get", ["https://a.example.com/a2a", "t2"], {})
            self.assertEqual(r["id"], "t2")


if __name__ == "__main__":
    unittest.main()
