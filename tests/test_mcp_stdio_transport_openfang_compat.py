"""Transport-level MCP stdio round-trip tests for ainl-mcp.

These tests spawn the actual stdio MCP server process and speak MCP JSON-RPC
using Content-Length framing (as implemented by the upstream OpenFang CLI/server).

We keep this optional at test time: if the MCP SDK isn't installed, the server
cannot boot and the test is skipped.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from typing import Any, Dict, Optional

import pytest


def _has_mcp_sdk() -> bool:
    try:
        import mcp.server.fastmcp  # noqa: F401

        return True
    except Exception:
        return False


def _write_line_json(w, payload: Dict[str, Any]) -> None:
    # Upstream OpenFang runtime's stdio MCP *client* transport is newline-delimited JSON-RPC.
    # (Its MCP *server* uses Content-Length framing, but that's the opposite direction.)
    line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    w.write(line)
    w.flush()


def _read_exact_with_timeout(r, n: int, timeout_s: float) -> bytes:
    out = bytearray()
    deadline = time.time() + timeout_s
    fd = r.fileno()
    while len(out) < n:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timeout reading {n} bytes (got {len(out)})")
        ready, _, _ = select.select([fd], [], [], min(0.25, remaining))
        if not ready:
            continue
        chunk = r.read(n - len(out))
        if not chunk:
            break
        out.extend(chunk)
    if len(out) != n:
        raise EOFError(f"unexpected EOF reading {n} bytes (got {len(out)})")
    return bytes(out)


def _read_framed(r, timeout_s: float = 5.0) -> Dict[str, Any]:
    # Read headers (Content-Length framing). Some MCP implementations use newline-delimited JSON
    # on stdio; we fall back to that if headers don't arrive.
    deadline = time.time() + timeout_s
    content_length: Optional[int] = None
    header_bytes = bytearray()
    fd = r.fileno()
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            # Fallback: try reading a newline-delimited JSON response.
            return _read_json_line(r, timeout_s=timeout_s)
        ready, _, _ = select.select([fd], [], [], min(0.25, remaining))
        if not ready:
            continue
        b = r.read(1)
        if not b:
            raise EOFError("EOF while reading MCP headers")
        # If the server speaks newline-delimited JSON, responses will typically start with '{'.
        if b == b"{":
            return _read_json_line(r, timeout_s=timeout_s, first_byte=b)
        header_bytes.extend(b)
        if header_bytes.endswith(b"\r\n\r\n"):
            break

    header_text = header_bytes.decode("ascii", errors="replace")
    for line in header_text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except Exception:
                content_length = None
    if not content_length or content_length <= 0:
        raise ValueError(f"missing/invalid Content-Length header: {header_text!r}")

    body = _read_exact_with_timeout(r, content_length, timeout_s=timeout_s)
    return json.loads(body.decode("utf-8"))


def _read_json_line(r, timeout_s: float, first_byte: bytes = b"") -> Dict[str, Any]:
    """Read a single JSON object terminated by newline."""
    fd = r.fileno()
    deadline = time.time() + timeout_s
    buf = bytearray()
    if first_byte:
        buf.extend(first_byte)
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("timeout waiting for MCP JSON line")
        ready, _, _ = select.select([fd], [], [], min(0.25, remaining))
        if not ready:
            continue
        chunk = r.readline()
        if not chunk:
            raise EOFError("EOF while reading MCP JSON line")
        buf.extend(chunk)
        # If line didn't include newline, keep reading; otherwise parse.
        if b"\n" in chunk:
            break
    return json.loads(buf.decode("utf-8"))


def _read_next_non_notification(r, timeout_s: float = 5.0) -> Dict[str, Any]:
    """Read messages until we get a response (has id) rather than a notification."""
    deadline = time.time() + timeout_s
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("timeout waiting for MCP response")
        msg = _read_json_line(r, timeout_s=remaining)
        if isinstance(msg, dict) and msg.get("id") is not None:
            return msg


@pytest.mark.skipif(not _has_mcp_sdk(), reason="mcp SDK not installed (ainl-mcp cannot boot)")
def test_openfang_style_mcp_stdio_roundtrip_initialize_list_call():
    # Spawn the MCP server in stdio mode. We use module execution so the test
    # does not depend on entrypoint resolution on PATH.
    env = dict(os.environ)
    # Keep it deterministic / low-risk during test runs.
    env.setdefault("AINL_MCP_PROFILE", "")
    env.setdefault("AINL_MCP_EXPOSURE_PROFILE", "minimal")
    env.setdefault("AINL_DRY_RUN", "1")

    proc = subprocess.Popen(
        [sys.executable, "-m", "scripts.ainl_mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdin and proc.stdout

    try:
        _write_line_json(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "openfang-test", "version": "0"},
                },
            },
        )
        init_resp = _read_next_non_notification(proc.stdout, timeout_s=10.0)
        assert init_resp.get("jsonrpc") == "2.0"
        assert init_resp.get("id") == 1
        assert "result" in init_resp

        # Notification: no response expected, but safe to send.
        _write_line_json(
            proc.stdin,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )

        _write_line_json(proc.stdin, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_resp = _read_next_non_notification(proc.stdout, timeout_s=10.0)
        assert tools_resp.get("id") == 2
        tools = (tools_resp.get("result") or {}).get("tools")
        assert isinstance(tools, list)
        names = {t.get("name") for t in tools if isinstance(t, dict)}
        # Minimal exposure should still include these core tools.
        assert "ainl_validate" in names
        assert "ainl_compile" in names

        _write_line_json(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "ainl_capabilities", "arguments": {}},
            },
        )
        call_resp = _read_next_non_notification(proc.stdout, timeout_s=15.0)
        assert call_resp.get("id") == 3
        # FastMCP returns MCP "content" envelopes; we just require success/no error.
        assert "error" not in call_resp
        assert "result" in call_resp
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
