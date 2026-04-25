#!/usr/bin/env python3
"""Minimal A2A HTTP bridge for ArmaraOS ↔ local Hermes operator workflows.

Serves:
  GET  /.well-known/agent.json   — Agent Card (ArmaraOS + Linux Foundation HTTP binding)
  POST /a2a                      — JSON-RPC 2.0: tasks/send, tasks/get (ArmaraOS-shaped)
  POST /message:send             — Linux Foundation HTTP+JSON (application/a2a+json)

Delegation: set ``HERMES_AINL_BRIDGE_CMD`` to a program that reads the user message on **stdin**
and writes the assistant reply on **stdout** (exit 0 on success). If unset, tasks complete with
a short help message so ArmaraOS can still discover and round-trip the wire.

No third-party dependencies (stdlib only).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


def _extract_user_text_from_armara_parts(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    parts = message.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("type") == "text" and "text" in p:
            chunks.append(str(p.get("text") or ""))
        elif "text" in p:
            chunks.append(str(p.get("text") or ""))
    return "\n".join(x for x in chunks if x).strip()


def _extract_user_text_from_a2a_http_message(message: Any) -> str:
    """A2A HTTP binding: parts may be [{\"text\": \"...\"}]."""
    if not isinstance(message, dict):
        return ""
    parts = message.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            chunks.append(str(p.get("text") or ""))
    return "\n".join(x for x in chunks if x).strip()


def _run_delegate(user_text: str) -> Tuple[str, bool]:
    cmd = (os.environ.get("HERMES_AINL_BRIDGE_CMD") or "").strip()
    if not cmd:
        help_txt = (
            "Hermes AINL ↔ ArmaraOS A2A bridge is running, but HERMES_AINL_BRIDGE_CMD is not set.\n"
            "Set it to a command that reads the user message on stdin and prints the reply on stdout.\n"
            "Example: export HERMES_AINL_BRIDGE_CMD='python3 /path/to/my_hermes_proxy.py'\n"
            "Then restart this bridge."
        )
        return help_txt, False
    timeout_s = int(os.environ.get("HERMES_AINL_BRIDGE_TIMEOUT_S") or "300")
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return f"Invalid HERMES_AINL_BRIDGE_CMD (shlex): {e}", True
    try:
        proc = subprocess.run(
            argv,
            input=(user_text or "") + "\n",
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "Bridge delegate timed out.", True
    except OSError as e:
        return f"Bridge delegate failed to start: {e}", True
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"Bridge delegate exit {proc.returncode}: {err[:800]}", True
    out = (proc.stdout or "").strip()
    return out if out else "(empty reply from delegate)", False


def _task_completed(task_id: str, session_id: Optional[str], reply: str) -> Dict[str, Any]:
    return {
        "id": task_id,
        "sessionId": session_id,
        "status": "completed",
        "messages": [
            {
                "role": "agent",
                "parts": [{"type": "text", "text": reply}],
            }
        ],
        "artifacts": [],
    }


def _task_failed(task_id: str, session_id: Optional[str], err: str) -> Dict[str, Any]:
    return {
        "id": task_id,
        "sessionId": session_id,
        "status": "failed",
        "messages": [
            {
                "role": "agent",
                "parts": [{"type": "text", "text": err}],
            }
        ],
        "artifacts": [],
    }


class BridgeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def put(self, task: Dict[str, Any]) -> None:
        tid = str(task.get("id") or "")
        if not tid:
            return
        with self._lock:
            self._tasks[tid] = task

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tasks.get(task_id)


STATE = BridgeState()


def _public_base_from_headers(handler: BaseHTTPRequestHandler, fallback_port: int) -> str:
    override = (os.environ.get("HERMES_AINL_BRIDGE_PUBLIC_BASE") or "").strip().rstrip("/")
    if override:
        return override
    scheme = (os.environ.get("HERMES_AINL_BRIDGE_PUBLIC_SCHEME") or "http").strip().lower()
    if scheme not in ("http", "https"):
        scheme = "http"
    host = handler.headers.get("Host")
    if host:
        return f"{scheme}://{host}"
    return f"http://127.0.0.1:{fallback_port}"


def _agent_card(public_base: str) -> Dict[str, Any]:
    b = public_base.rstrip("/")
    return {
        "name": "HermesAINLArmaraBridge",
        "description": "AINL-packaged A2A shim for ArmaraOS: JSON-RPC tasks/send + HTTP message:send. "
        "Set HERMES_AINL_BRIDGE_CMD to pipe tasks to Hermes or another backend.",
        "url": f"{b}/a2a",
        "version": "0.1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "skills": [
            {
                "id": "bridge_delegate",
                "name": "Delegate via HERMES_AINL_BRIDGE_CMD",
                "description": "Runs operator-configured stdin/stdout delegate.",
                "tags": ["ainl", "armaraos", "bridge"],
                "examples": ["Summarize my inbox rules"],
            }
        ],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "supportedInterfaces": [
            {
                "url": b,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "0.3",
            }
        ],
    }


def make_handler(fallback_port: int):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            if os.environ.get("HERMES_AINL_BRIDGE_QUIET") == "1":
                return
            super().log_message(fmt, *args)

        def _read_json_body(self) -> Any:
            n = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(n) if n > 0 else b""
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, code: int, obj: Any) -> None:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/.well-known/agent.json":
                base = _public_base_from_headers(self, fallback_port)
                self._send_json(200, _agent_card(base))
            else:
                self.send_error(404, "Not found")

        def _handle_tasks_send(self, req_id: Any, params: Any) -> Dict[str, Any]:
            if not isinstance(params, dict):
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Invalid params"}}
            msg = params.get("message")
            session_id = params.get("sessionId")
            if isinstance(session_id, str) and not session_id.strip():
                session_id = None
            text = _extract_user_text_from_armara_parts(msg)
            task_id = str(uuid.uuid4())
            reply, is_err = _run_delegate(text)
            task = _task_failed(task_id, session_id, reply) if is_err else _task_completed(task_id, session_id, reply)
            STATE.put(task)
            return {"jsonrpc": "2.0", "id": req_id, "result": task}

        def _handle_tasks_get(self, req_id: Any, params: Any) -> Dict[str, Any]:
            if not isinstance(params, dict):
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Invalid params"}}
            tid = params.get("id")
            if not isinstance(tid, str) or not tid:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing task id"}}
            t = STATE.get(tid)
            if t is None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32001, "message": "Task not found"},
                }
            return {"jsonrpc": "2.0", "id": req_id, "result": t}

        def do_POST(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            ct = (self.headers.get("Content-Type") or "").lower()

            if path == "/message:send" or path.endswith("/message:send"):
                if "application/a2a+json" not in ct and "application/json" not in ct:
                    self.send_error(415, "Expected application/a2a+json")
                    return
                try:
                    body = self._read_json_body()
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                if not isinstance(body, dict):
                    self.send_error(400, "Invalid JSON")
                    return
                msg = body.get("message")
                text = _extract_user_text_from_a2a_http_message(msg)
                task_id = str(uuid.uuid4())
                reply, is_err = _run_delegate(text)
                task = _task_failed(task_id, None, reply) if is_err else _task_completed(task_id, None, reply)
                STATE.put(task)
                self._send_json(200, {"task": task})
                return

            if path == "/a2a" or path.endswith("/a2a"):
                try:
                    body = self._read_json_body()
                except Exception as e:
                    self._send_json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}})
                    return
                if not isinstance(body, dict):
                    self.send_error(400, "Invalid JSON-RPC")
                    return
                req_id = body.get("id")
                method = body.get("method")
                params = body.get("params")
                if method == "tasks/send":
                    self._send_json(200, self._handle_tasks_send(req_id, params))
                elif method == "tasks/get":
                    self._send_json(200, self._handle_tasks_get(req_id, params))
                else:
                    self._send_json(
                        200,
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": f"Method not found: {method!r}"},
                        },
                    )
                return

            self.send_error(404, "Not found")

    return H


def main() -> None:
    host = os.environ.get("HERMES_AINL_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("HERMES_AINL_BRIDGE_PORT", "18765"))
    server = ThreadingHTTPServer((host, port), make_handler(port))
    print(f"AINL Hermes ↔ ArmaraOS A2A bridge on http://{host}:{port}/", flush=True)
    print("  GET  /.well-known/agent.json", flush=True)
    print("  POST /a2a  (JSON-RPC tasks/send | tasks/get)", flush=True)
    print("  POST /message:send  (application/a2a+json)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
