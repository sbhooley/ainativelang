"""Tests for adapters/browser.py (HTTP proxy to ArmaraOS browser_* tools).

These are pure unit tests — we monkeypatch ``urllib.request.urlopen`` so no
ArmaraOS daemon needs to be running and no real browser is launched. They
verify:

* Verb → tool name mapping (incl. case/separator aliases).
* Argument shaping for each verb (URL, selector, mode, etc).
* Per-call ``mode`` override for ``NAVIGATE`` and ``SESSION_START``.
* MCP envelope unwrapping (text content, isError, JSON-RPC error).
* JSON-decoded result for ``SESSION_STATUS``.
* Helpful error when the daemon is unreachable.
* Headers (Bearer auth, X-Agent-Id) are sent.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import pytest

from adapters.browser import BrowserAdapter
from runtime.adapters.base import AdapterError


# ── helpers ────────────────────────────────────────────────────────────


class _FakeResponse:
    """Stand-in for the context manager returned by urllib.request.urlopen."""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _Recorder:
    """Captures the urllib.request.Request that the adapter built."""

    def __init__(self, response_payload: Dict[str, Any]):
        self.requests: List[urllib.request.Request] = []
        self.bodies: List[Dict[str, Any]] = []
        self._payload = response_payload

    def __call__(self, req: urllib.request.Request, timeout: float):
        self.requests.append(req)
        if req.data:
            self.bodies.append(json.loads(req.data.decode("utf-8")))
        return _FakeResponse(self._payload)


def _ok_envelope(text: str = "ok", *, is_error: bool = False) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        },
    }


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Don't let the test host's ARMARAOS_* env leak into the adapter."""
    for key in (
        "ARMARAOS_API_BASE",
        "ARMARAOS_API_KEY",
        "AINL_BROWSER_AGENT_ID",
        "AINL_BROWSER_TIMEOUT_S",
    ):
        monkeypatch.delenv(key, raising=False)


# ── verb mapping ───────────────────────────────────────────────────────


def test_navigate_maps_to_browser_navigate_with_url(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("navigated"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    out = BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})

    assert out == "navigated"
    assert len(rec.bodies) == 1
    body = rec.bodies[0]
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "browser_navigate"
    assert body["params"]["arguments"] == {"url": "https://example.com"}


def test_navigate_per_call_mode_override(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter().call("navigate", ["https://example.com", "headed"], {})

    assert rec.bodies[0]["params"]["arguments"] == {
        "url": "https://example.com",
        "mode": "headed",
    }


def test_navigate_blank_mode_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter().call("navigate", ["https://example.com", "   "], {})

    assert rec.bodies[0]["params"]["arguments"] == {"url": "https://example.com"}


@pytest.mark.parametrize(
    "verb,args,expected_tool,expected_args",
    [
        ("CLICK", ["#submit"], "browser_click", {"selector": "#submit"}),
        ("TYPE", ["input[name=q]", "hello"], "browser_type", {"selector": "input[name=q]", "text": "hello"}),
        ("READ_PAGE", [], "browser_read_page", {}),
        ("read", [], "browser_read_page", {}),
        ("SCREENSHOT", [], "browser_screenshot", {}),
        ("CLOSE", [], "browser_close", {}),
        ("BACK", [], "browser_back", {}),
        ("SCROLL", ["down", 600], "browser_scroll", {"direction": "down", "amount": 600}),
        ("WAIT", ["#results", 5000], "browser_wait", {"selector": "#results", "timeout_ms": 5000}),
        ("RUN_JS", ["document.title"], "browser_run_js", {"expression": "document.title"}),
        ("SESSION_START", ["headed"], "browser_session_start", {"mode": "headed"}),
        ("SESSION_START", [], "browser_session_start", {}),
        ("SESSION_STATUS", [], "browser_session_status", {}),
        ("status", [], "browser_session_status", {}),
        ("session-status", [], "browser_session_status", {}),
    ],
)
def test_verb_mapping(
    monkeypatch: pytest.MonkeyPatch,
    verb: str,
    args: List[Any],
    expected_tool: str,
    expected_args: Dict[str, Any],
) -> None:
    rec = _Recorder(_ok_envelope("{}" if expected_tool == "browser_session_status" else "ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter().call(verb, args, {})

    body = rec.bodies[0]
    assert body["params"]["name"] == expected_tool
    assert body["params"]["arguments"] == expected_args


def test_unknown_verb_raises_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(_ok_envelope("ok")))

    with pytest.raises(AdapterError) as exc:
        BrowserAdapter().call("DANCE", ["selector"], {})

    msg = str(exc.value)
    assert "browser adapter unsupported target" in msg
    assert "browser_navigate" in msg


# ── argument validation ────────────────────────────────────────────────


def test_navigate_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(_ok_envelope("ok")))
    with pytest.raises(AdapterError, match="requires a URL"):
        BrowserAdapter().call("NAVIGATE", [], {})


def test_type_requires_two_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(_ok_envelope("ok")))
    with pytest.raises(AdapterError, match=r"requires \(selector, text\)"):
        BrowserAdapter().call("TYPE", ["#x"], {})


def test_scroll_amount_must_be_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(_ok_envelope("ok")))
    with pytest.raises(AdapterError, match="amount must be an integer"):
        BrowserAdapter().call("SCROLL", ["down", "lots"], {})


def test_wait_timeout_must_be_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(_ok_envelope("ok")))
    with pytest.raises(AdapterError, match="timeout_ms must be an integer"):
        BrowserAdapter().call("WAIT", ["#x", "soon"], {})


# ── envelope unwrapping ───────────────────────────────────────────────


def test_session_status_decodes_json_text(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "agent_id": "ainl-default",
                            "active": True,
                            "mode": "headless",
                            "chromium_available": True,
                            "available_modes": ["headless", "headed"],
                        }
                    ),
                }
            ],
            "isError": False,
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(payload))

    out = BrowserAdapter().call("SESSION_STATUS", [], {})

    assert isinstance(out, dict)
    assert out["mode"] == "headless"
    assert out["chromium_available"] is True


def test_is_error_envelope_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _ok_envelope("Chromium not found in PATH", is_error=True)
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(payload))

    with pytest.raises(AdapterError, match="Chromium not found"):
        BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})


def test_jsonrpc_error_envelope_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "Method not found"},
    }
    monkeypatch.setattr(urllib.request, "urlopen", _Recorder(payload))

    with pytest.raises(AdapterError, match="Method not found"):
        BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})


# ── transport / config ────────────────────────────────────────────────


def test_url_and_headers_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter(
        base_url="http://daemon.local:9999/",
        api_key="topsecret",
        agent_id="agent-42",
    ).call("NAVIGATE", ["https://example.com"], {})

    req = rec.requests[0]
    assert req.full_url == "http://daemon.local:9999/mcp"
    assert req.get_method() == "POST"
    assert req.get_header("Content-type") == "application/json"
    assert req.get_header("Authorization") == "Bearer topsecret"
    assert req.get_header("X-agent-id") == "agent-42"


def test_url_error_surfaces_actionable_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(req: urllib.request.Request, timeout: float):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    with pytest.raises(AdapterError) as exc:
        BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})

    assert "cannot reach ArmaraOS" in str(exc.value)
    assert "openfang start" in str(exc.value)


def test_http_error_includes_status_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(req: urllib.request.Request, timeout: float):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error":"missing token"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    with pytest.raises(AdapterError) as exc:
        BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})

    msg = str(exc.value)
    assert "HTTP 401" in msg
    assert "missing token" in msg
    assert "ARMARAOS_API_KEY" in msg


def test_default_agent_id_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})

    assert rec.requests[0].get_header("X-agent-id") == "ainl-default"


def test_env_overrides_pickup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARMARAOS_API_BASE", "http://other:1234")
    monkeypatch.setenv("ARMARAOS_API_KEY", "envkey")
    monkeypatch.setenv("AINL_BROWSER_AGENT_ID", "from-env")
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    BrowserAdapter().call("NAVIGATE", ["https://example.com"], {})

    req = rec.requests[0]
    assert req.full_url == "http://other:1234/mcp"
    assert req.get_header("Authorization") == "Bearer envkey"
    assert req.get_header("X-agent-id") == "from-env"


# ── ID monotonicity ───────────────────────────────────────────────────


def test_request_ids_are_monotonic(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(_ok_envelope("ok"))
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    adapter = BrowserAdapter()
    adapter.call("NAVIGATE", ["https://a"], {})
    adapter.call("NAVIGATE", ["https://b"], {})
    adapter.call("CLICK", ["#x"], {})

    ids = [b["id"] for b in rec.bodies]
    assert ids == [1, 2, 3]
