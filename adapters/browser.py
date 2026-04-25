"""AINL `browser` adapter — drives a real Chrome/Chromium browser via ArmaraOS.

This adapter is a **thin HTTP proxy** to an ArmaraOS daemon's MCP endpoint
(`POST /mcp`). It does **not** spawn or speak CDP itself. The actual browser
lifecycle and CDP plumbing live in the ArmaraOS Rust runtime
(`armaraos/crates/openfang-runtime/src/browser.rs`) so there is exactly one
implementation of browser automation across the whole stack.

Why a proxy and not a local CDP client?
* Single source of truth — Rust handles spawn / attach / mode switching /
  Chromium discovery; Python doesn't duplicate any of that.
* ArmaraOS is already the daemon that scheduled `ainl run` and the desktop
  agent loop run inside, so the daemon is reachable on `127.0.0.1:4200` in
  every common deployment.
* If the user runs `ainl run` standalone without ArmaraOS, the adapter
  fails fast with an actionable error pointing them at the install.

Verbs map 1:1 to the ArmaraOS `browser_*` tool family:

    R browser.NAVIGATE "https://example.com" ->page
    R browser.NAVIGATE "https://example.com" "headed" ->page    # per-call mode
    R browser.SESSION_START "headed" ->status
    R browser.SESSION_STATUS ->status
    R browser.READ_PAGE ->content
    R browser.CLICK "#submit-btn" ->_
    R browser.TYPE "input[name='email']" "user@example.com" ->_
    R browser.SCREENSHOT ->png_b64
    R browser.SCROLL "down" 600 ->_
    R browser.WAIT "#results" 5000 ->_
    R browser.RUN_JS "document.title" ->title
    R browser.BACK ->_
    R browser.CLOSE ->_

Configuration (env vars):
* ``ARMARAOS_API_BASE`` — daemon URL. Default: ``http://127.0.0.1:4200``.
* ``ARMARAOS_API_KEY``  — bearer token if the daemon requires auth.
* ``AINL_BROWSER_AGENT_ID`` — agent id used to tag the browser session
  inside ArmaraOS. Defaults to ``ainl-default``. Different ids get separate
  browser sessions, the same id reuses one across calls.
* ``AINL_BROWSER_TIMEOUT_S`` — per-request HTTP timeout. Default ``60``.

The adapter raises :class:`AdapterError` (handled by the AINL runtime) on
network failures, daemon errors, or invalid arguments.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter

logger = logging.getLogger(__name__)


# Map AINL adapter verbs (case-insensitive) → ArmaraOS tool name.
# Adding a new verb here is the only place that should change when a new
# `browser_*` tool ships in ArmaraOS.
_VERB_TO_TOOL = {
    "navigate": "browser_navigate",
    "click": "browser_click",
    "type": "browser_type",
    "screenshot": "browser_screenshot",
    "read_page": "browser_read_page",
    "readpage": "browser_read_page",
    "read": "browser_read_page",
    "close": "browser_close",
    "scroll": "browser_scroll",
    "wait": "browser_wait",
    "run_js": "browser_run_js",
    "runjs": "browser_run_js",
    "js": "browser_run_js",
    "back": "browser_back",
    "session_start": "browser_session_start",
    "sessionstart": "browser_session_start",
    "start": "browser_session_start",
    "session_status": "browser_session_status",
    "sessionstatus": "browser_session_status",
    "status": "browser_session_status",
}


def _default_base() -> str:
    return (os.getenv("ARMARAOS_API_BASE") or "http://127.0.0.1:4200").rstrip("/")


def _default_agent_id() -> str:
    aid = (os.getenv("AINL_BROWSER_AGENT_ID") or "").strip()
    return aid or "ainl-default"


def _default_timeout() -> float:
    raw = (os.getenv("AINL_BROWSER_TIMEOUT_S") or "").strip()
    if not raw:
        return 60.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 60.0


class BrowserAdapter(RuntimeAdapter):
    """Proxy AINL ``R browser.*`` calls to ArmaraOS's CDP browser tools."""

    group = "browser"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self._base_url = (base_url or _default_base()).rstrip("/")
        self._api_key = api_key if api_key is not None else os.getenv("ARMARAOS_API_KEY")
        self._agent_id = agent_id or _default_agent_id()
        self._timeout_s = float(timeout_s) if timeout_s is not None else _default_timeout()
        self._next_id = 0

    # ── Public API ─────────────────────────────────────────────────────

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        """Synchronous dispatch — translates verb+args → MCP tool call."""
        tool, arguments = self._build_tool_call(target, args)
        return self._invoke(tool, arguments)

    # ── Verb / argument mapping ────────────────────────────────────────

    def _build_tool_call(self, target: str, args: List[Any]) -> tuple[str, Dict[str, Any]]:
        verb = (target or "").strip().lower().replace("-", "_")
        tool = _VERB_TO_TOOL.get(verb)
        if tool is None:
            raise AdapterError(
                f"browser adapter unsupported target: {target!r}. "
                f"Use one of: {sorted(set(_VERB_TO_TOOL.values()))}"
            )

        a = list(args or [])

        if tool == "browser_navigate":
            if not a or not isinstance(a[0], str):
                raise AdapterError("browser.NAVIGATE requires a URL string")
            arguments: Dict[str, Any] = {"url": a[0]}
            if len(a) >= 2 and isinstance(a[1], str) and a[1].strip():
                arguments["mode"] = a[1].strip()
            return tool, arguments

        if tool == "browser_click":
            if not a or not isinstance(a[0], str):
                raise AdapterError("browser.CLICK requires a CSS selector or visible text")
            return tool, {"selector": a[0]}

        if tool == "browser_type":
            if len(a) < 2 or not isinstance(a[0], str):
                raise AdapterError("browser.TYPE requires (selector, text)")
            return tool, {"selector": a[0], "text": str(a[1])}

        if tool == "browser_scroll":
            arguments = {}
            if a and isinstance(a[0], str):
                arguments["direction"] = a[0]
            if len(a) >= 2:
                try:
                    arguments["amount"] = int(a[1])
                except (TypeError, ValueError):
                    raise AdapterError("browser.SCROLL amount must be an integer")
            return tool, arguments

        if tool == "browser_wait":
            if not a or not isinstance(a[0], str):
                raise AdapterError("browser.WAIT requires a CSS selector")
            arguments = {"selector": a[0]}
            if len(a) >= 2:
                try:
                    arguments["timeout_ms"] = int(a[1])
                except (TypeError, ValueError):
                    raise AdapterError("browser.WAIT timeout_ms must be an integer")
            return tool, arguments

        if tool == "browser_run_js":
            if not a or not isinstance(a[0], str):
                raise AdapterError("browser.RUN_JS requires a JavaScript expression")
            return tool, {"expression": a[0]}

        if tool == "browser_session_start":
            arguments = {}
            if a and isinstance(a[0], str) and a[0].strip():
                arguments["mode"] = a[0].strip()
            return tool, arguments

        # browser_screenshot, browser_read_page, browser_close, browser_back,
        # browser_session_status — no args.
        return tool, {}

    # ── Wire layer (MCP HTTP, stdlib only — no requests dependency) ────

    def _invoke(self, tool: str, arguments: Dict[str, Any]) -> Any:
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        body = json.dumps(payload).encode("utf-8")

        url = f"{self._base_url}/mcp"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if self._api_key:
            req.add_header("Authorization", f"Bearer {self._api_key}")
        # Tag every browser session with the configured agent id so the
        # server can route to the same BrowserSession across calls.
        req.add_header("X-Agent-Id", self._agent_id)

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            raise AdapterError(
                f"browser adapter HTTP {e.code} from {url}: {e.reason}. "
                f"Body: {err_body}. "
                f"Hint: ensure the ArmaraOS daemon is running and ARMARAOS_API_KEY is set if it requires auth."
            )
        except urllib.error.URLError as e:
            raise AdapterError(
                f"browser adapter cannot reach ArmaraOS at {url}: {e.reason}. "
                f"Start the daemon (`openfang start`) or set ARMARAOS_API_BASE to point at a reachable instance."
            )
        except TimeoutError:
            raise AdapterError(
                f"browser adapter timed out after {self._timeout_s:.0f}s calling {tool}. "
                f"Increase AINL_BROWSER_TIMEOUT_S or check that Chrome is responsive."
            )

        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AdapterError(f"browser adapter: ArmaraOS returned non-JSON: {e}")

        return self._extract_result(tool, envelope)

    @staticmethod
    def _extract_result(tool: str, envelope: Dict[str, Any]) -> Any:
        """Pull the tool output text out of an MCP JSON-RPC response.

        MCP responses look like::

            {"jsonrpc":"2.0","id":1,
             "result":{"content":[{"type":"text","text":"..."}],"isError":false}}

        On error we either get ``"error": {...}`` or
        ``"result": {..., "isError": true}``. We surface both as AdapterError.
        """
        if not isinstance(envelope, dict):
            raise AdapterError(f"browser adapter: unexpected response shape: {envelope!r}")

        if "error" in envelope:
            err = envelope["error"]
            if isinstance(err, dict):
                msg = err.get("message") or json.dumps(err)
            else:
                msg = str(err)
            raise AdapterError(f"browser adapter: ArmaraOS error for {tool}: {msg}")

        result = envelope.get("result")
        if not isinstance(result, dict):
            raise AdapterError(
                f"browser adapter: malformed MCP envelope for {tool}: missing 'result' object"
            )

        is_error = bool(result.get("isError"))
        content = result.get("content")
        text = ""
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                text = str(first.get("text") or "")

        if is_error:
            raise AdapterError(
                f"browser adapter: {tool} failed: {text or 'no error detail returned'}"
            )

        # browser_session_status returns JSON-encoded text — parse for callers.
        if tool == "browser_session_status":
            stripped = text.strip()
            if stripped.startswith("{"):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    return text
        return text


__all__ = ["BrowserAdapter"]
