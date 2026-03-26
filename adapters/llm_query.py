"""
Lightweight LLM query adapter for ad-hoc prompt calls from AINL R steps.

Enable via either:
  - CLI: --enable-adapter llm_query
  - Env: AINL_ENABLE_LLM_QUERY=true

Env:
  - AINL_LLM_QUERY_URL: HTTP endpoint for LLM query bridge (recommended)
  - AINL_LLM_QUERY_MOCK: when truthy, returns deterministic mock response
  - AINL_LLM_QUERY_CMD: optional subprocess fallback command
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


class LlmQueryAdapter(RuntimeAdapter):
    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        runner_url: Optional[str] = None,
        allow_hosts: Optional[Iterable[str]] = None,
        timeout_s: float = 30.0,
        max_response_bytes: int = 1_000_000,
    ):
        self._enabled = _is_truthy_env(os.environ.get("AINL_ENABLE_LLM_QUERY")) if enabled is None else bool(enabled)
        self._runner_url = str(runner_url or os.environ.get("AINL_LLM_QUERY_URL") or "").strip()
        self._allow_hosts = set(str(h).strip() for h in (allow_hosts or []) if str(h).strip())
        self._timeout_s = float(timeout_s)
        self._max_response_bytes = int(max_response_bytes)
        self._mock_mode = _is_truthy_env(os.environ.get("AINL_LLM_QUERY_MOCK"))
        self._fallback_cmd = str(os.environ.get("AINL_LLM_QUERY_CMD") or "").strip()

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise AdapterError("llm_query disabled; enable with --enable-adapter llm_query or AINL_ENABLE_LLM_QUERY=true")

    def _validate_host(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise AdapterError("llm_query requires http/https AINL_LLM_QUERY_URL")
        if self._allow_hosts and parsed.hostname not in self._allow_hosts:
            raise AdapterError(f"llm_query host blocked by allowlist: {parsed.hostname}")

    def _post_http(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._runner_url:
            raise AdapterError("llm_query missing AINL_LLM_QUERY_URL")
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
                    raise AdapterError("llm_query response too large")
                text = body.decode("utf-8", errors="replace")
                parsed: Any
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = {"raw": text}
                return {"ok": 200 <= status < 300, "status_code": status, "body": parsed}
        except Exception as e:
            raise AdapterError(f"llm_query http error: {e}") from e

    def _run_subprocess(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._fallback_cmd:
            raise AdapterError("llm_query unavailable: set AINL_LLM_QUERY_URL or AINL_LLM_QUERY_CMD")
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
            raise AdapterError(f"llm_query subprocess error: {e}") from e
        if proc.returncode != 0:
            raise AdapterError(f"llm_query subprocess failed: {proc.stderr.strip()}")
        try:
            body = json.loads(proc.stdout.strip() or "{}")
        except Exception:
            body = {"raw": proc.stdout}
        return {"ok": True, "status_code": 0, "body": body}

    def run(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._ensure_enabled()
        safe_context = _strip_private_keys(dict(context or {}))
        payload: Dict[str, Any] = {"prompt": str(prompt), "context": safe_context}
        if model is not None:
            payload["model"] = str(model)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        if self._mock_mode:
            return {
                "ok": True,
                "runtime": "llm_query",
                "result": {"mock": True, "text": f"MOCK:{prompt}"},
                "traces": [{"event": "llm_query.mock", "prompt_len": len(str(prompt))}],
            }

        result = self._post_http(payload) if self._runner_url else self._run_subprocess(payload)
        body = result.get("body")
        traces: List[Any] = []
        out: Any = body
        if isinstance(body, dict):
            if isinstance(body.get("traces"), list):
                traces = body.get("traces", [])
            if "result" in body:
                out = body.get("result")
        return {
            "ok": bool(result.get("ok", False)),
            "runtime": "llm_query",
            "status_code": result.get("status_code"),
            "result": out,
            "traces": traces,
        }

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().upper()
        if verb not in {"QUERY", "RUN"}:
            raise AdapterError(f"llm_query unsupported verb: {target!r}")
        if not args:
            raise AdapterError("llm_query requires prompt argument")
        prompt = str(args[0])
        model = str(args[1]) if len(args) > 1 and args[1] is not None else None
        max_tokens: Optional[int] = None
        if len(args) > 2 and args[2] is not None:
            try:
                max_tokens = int(args[2])
            except Exception as e:
                raise AdapterError(f"llm_query invalid max_tokens: {args[2]!r}") from e
        return self.run(prompt, model=model, max_tokens=max_tokens, context=context)
