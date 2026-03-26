"""
PTC Runner adapter for executing PTC-Lisp snippets from AINL R steps.

Enable via either:
  - CLI: --enable-adapter ptc_runner
  - Env: AINL_ENABLE_PTC=true

Env:
  - AINL_PTC_RUNNER_URL: HTTP endpoint for PTC runner (recommended)
  - AINL_PTC_RUNNER_MOCK: when truthy, returns deterministic mock response
  - AINL_PTC_RUNNER_CMD: optional subprocess fallback command

AINL examples:
  R ptc_runner run "(+ 1 2)" "{total :float}" 5 ->out
  R ptc_runner.RUN "(+ 1 2)" "{total :float}" 5 ->out
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from runtime.adapters.base import AdapterError, RuntimeAdapter


def _is_truthy_env(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _strip_private_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_private_keys(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_strip_private_keys(v) for v in value]
    return value


class PtcRunnerAdapter(RuntimeAdapter):
    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        runner_url: Optional[str] = None,
        allow_hosts: Optional[Iterable[str]] = None,
        timeout_s: float = 30.0,
        max_response_bytes: int = 1_000_000,
    ):
        self._enabled = _is_truthy_env(os.environ.get("AINL_ENABLE_PTC")) if enabled is None else bool(enabled)
        self._runner_url = str(runner_url or os.environ.get("AINL_PTC_RUNNER_URL") or "").strip()
        self._allow_hosts = set(str(h).strip() for h in (allow_hosts or []) if str(h).strip())
        self._timeout_s = float(timeout_s)
        self._max_response_bytes = int(max_response_bytes)
        self._mock_mode = _is_truthy_env(os.environ.get("AINL_PTC_RUNNER_MOCK"))
        self._fallback_cmd = str(os.environ.get("AINL_PTC_RUNNER_CMD") or "").strip()

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise AdapterError("ptc_runner disabled; enable with --enable-adapter ptc_runner or AINL_ENABLE_PTC=true")

    def _validate_host(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise AdapterError("ptc_runner requires http/https AINL_PTC_RUNNER_URL")
        if self._allow_hosts and parsed.hostname not in self._allow_hosts:
            raise AdapterError(f"ptc_runner host blocked by allowlist: {parsed.hostname}")

    def _post_http(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._runner_url:
            raise AdapterError("ptc_runner missing AINL_PTC_RUNNER_URL")
        self._validate_host(self._runner_url)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            url=self._runner_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self._timeout_s) as resp:
                status = int(getattr(resp, "status", 200))
                body = resp.read(self._max_response_bytes + 1)
                if len(body) > self._max_response_bytes:
                    raise AdapterError("ptc_runner response too large")
                text = body.decode("utf-8", errors="replace")
                parsed: Any
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = {"raw": text}
                return {"ok": 200 <= status < 300, "status_code": status, "body": parsed}
        except Exception as e:
            raise AdapterError(f"ptc_runner http error: {e}") from e

    def _run_subprocess(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._fallback_cmd:
            raise AdapterError("ptc_runner unavailable: set AINL_PTC_RUNNER_URL or AINL_PTC_RUNNER_CMD")
        try:
            proc = subprocess.run(
                [self._fallback_cmd],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self._timeout_s,
                check=False,
            )
        except Exception as e:
            raise AdapterError(f"ptc_runner subprocess error: {e}") from e
        if proc.returncode != 0:
            raise AdapterError(f"ptc_runner subprocess failed: {proc.stderr.strip()}")
        try:
            body = json.loads(proc.stdout.strip() or "{}")
        except Exception:
            body = {"raw": proc.stdout}
        return {"ok": True, "status_code": 0, "body": body}

    def run(
        self,
        lisp: str,
        *,
        signature: Optional[str] = None,
        subagent_budget: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._ensure_enabled()
        payload: Dict[str, Any] = {
            "lisp": str(lisp),
            "context": _strip_private_keys(dict(context or {})),
        }
        if signature is not None:
            payload["signature"] = str(signature)
        if subagent_budget is not None:
            payload["subagent_budget"] = int(subagent_budget)

        if self._mock_mode:
            traces = [
                {
                    "event": "ptc_runner.mock",
                    "lisp_len": len(payload["lisp"]),
                }
            ]
            return {
                "ok": True,
                "runtime": "ptc_runner",
                "result": {"mock": True, "value": payload["lisp"]},
                "traces": traces,
            }

        http_result: Dict[str, Any]
        if self._runner_url:
            http_result = self._post_http(payload)
        else:
            http_result = self._run_subprocess(payload)

        body = http_result.get("body")
        traces: List[Any] = []
        result: Any = body
        if isinstance(body, dict):
            maybe_traces = body.get("traces")
            if isinstance(maybe_traces, list):
                traces = maybe_traces
            if "result" in body:
                result = body.get("result")

        return {
            "ok": bool(http_result.get("ok", False)),
            "runtime": "ptc_runner",
            "status_code": http_result.get("status_code"),
            "result": result,
            "traces": traces,
        }

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().upper()
        if verb not in {"RUN"}:
            raise AdapterError(f"ptc_runner unsupported verb: {target!r}")
        if not args:
            raise AdapterError("ptc_runner.RUN requires at least lisp source argument")

        lisp = str(args[0])
        signature = str(args[1]) if len(args) > 1 and args[1] is not None else None
        budget: Optional[int] = None
        if len(args) > 2 and args[2] is not None:
            try:
                budget = int(args[2])
            except Exception as e:
                raise AdapterError(f"ptc_runner.RUN invalid subagent_budget: {args[2]!r}") from e
        return self.run(lisp, signature=signature, subagent_budget=budget, context=context)
