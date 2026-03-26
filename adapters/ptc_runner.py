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
from urllib.parse import urlparse, urlunparse
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


def _normalize_beam_metrics(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    if "heap_bytes" in value:
        out["heap_bytes"] = value.get("heap_bytes")
    elif "heap" in value:
        out["heap_bytes"] = value.get("heap")
    if "reductions" in value:
        out["reductions"] = value.get("reductions")
    if "exec_time_ms" in value:
        out["exec_time_ms"] = value.get("exec_time_ms")
    elif "execution_time_ms" in value:
        out["exec_time_ms"] = value.get("execution_time_ms")
    if "pid" in value:
        out["pid"] = value.get("pid")
    elif "process_id" in value:
        out["pid"] = value.get("process_id")
    return out


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
        self._metrics_path = str(os.environ.get("AINL_PTC_METRICS_PATH") or "").strip()
        # Optional deeper BEAM integration: when truthy, prefer subprocess mode
        # for `run` calls when a fallback command is configured.
        self._use_subprocess = _is_truthy_env(os.environ.get("AINL_PTC_USE_SUBPROCESS"))

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

    def _get_http(self, url: str) -> Dict[str, Any]:
        self._validate_host(url)
        req = Request(url=url, headers={"Accept": "application/json"}, method="GET")
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

    def _metrics_url(self) -> Optional[str]:
        if not self._runner_url or not self._metrics_path:
            return None
        parsed = urlparse(self._runner_url)
        path = self._metrics_path if self._metrics_path.startswith("/") else f"/{self._metrics_path}"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

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
        ok = proc.returncode == 0
        text = proc.stdout.strip() if ok else proc.stderr.strip()
        body: Any
        if ok:
            try:
                body = json.loads(text or "{}")
            except Exception:
                body = {"raw": proc.stdout}
        else:
            body = {
                "error": text or "ptc_runner subprocess failed",
                "stderr": proc.stderr.strip(),
            }
        return {"ok": ok, "status_code": proc.returncode, "body": body}

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
                "beam_metrics": {},
                "traces": traces,
            }

        http_result: Dict[str, Any]
        if self._use_subprocess and self._fallback_cmd:
            http_result = self._run_subprocess(payload)
        elif self._runner_url:
            http_result = self._post_http(payload)
        else:
            http_result = self._run_subprocess(payload)

        body = http_result.get("body")
        traces: List[Any] = []
        result: Any = body
        beam_metrics: Dict[str, Any] = {}
        beam_telemetry: Dict[str, Any] = {}
        if isinstance(body, dict):
            maybe_traces = body.get("traces")
            if isinstance(maybe_traces, list):
                traces = maybe_traces
            if "result" in body:
                result = body.get("result")
            if isinstance(body.get("beam_telemetry"), dict):
                beam_telemetry = body["beam_telemetry"]
            beam_metrics = _normalize_beam_metrics(body.get("beam_metrics"))
            if not beam_metrics and isinstance(result, dict):
                beam_metrics = _normalize_beam_metrics(result.get("beam_metrics"))
                if isinstance(result.get("beam_telemetry"), dict):
                    beam_telemetry = result["beam_telemetry"]

        return {
            "ok": bool(http_result.get("ok", False)),
            "runtime": "ptc_runner",
            "status_code": http_result.get("status_code"),
            "result": result,
            "beam_metrics": beam_metrics,
            "beam_telemetry": beam_telemetry,
            "traces": traces,
        }

    def health(self, *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_enabled()
        if self._mock_mode:
            return {
                "ok": True,
                "runtime": "ptc_runner",
                "status_code": 200,
                "result": {"beam_status": "running", "mock": True},
                "beam_metrics": {"heap_bytes": 0, "reductions": 0, "exec_time_ms": 0, "pid": "mock"},
                "traces": [{"event": "ptc_runner.health.mock"}],
            }
        if not self._runner_url:
            raise AdapterError("ptc_runner missing AINL_PTC_RUNNER_URL")
        ping = self._get_http(self._runner_url)
        metrics_url = self._metrics_url()
        beam_metrics: Dict[str, Any] = {}
        if metrics_url:
            try:
                metrics_res = self._get_http(metrics_url)
                metrics_body = metrics_res.get("body")
                if isinstance(metrics_body, dict):
                    beam_metrics = _normalize_beam_metrics(metrics_body.get("beam_metrics") or metrics_body)
            except AdapterError:
                beam_metrics = {}
        return {
            "ok": bool(ping.get("ok", False)),
            "runtime": "ptc_runner",
            "status_code": ping.get("status_code"),
            "result": {"beam_status": "running" if ping.get("ok", False) else "degraded"},
            "beam_metrics": beam_metrics,
            "traces": [{"event": "ptc_runner.health"}],
        }

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().upper()
        if verb in {"HEALTH", "STATUS"}:
            return self.health(context=context)
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
