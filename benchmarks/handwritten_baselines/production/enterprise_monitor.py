"""
Production-grade baseline-B implementation: enterprise infrastructure health
monitor — semantically equivalent to examples/benchmark/enterprise_monitor.ainl.

Adds the structural surface a senior engineer would ship before going to
production: typed retry/backoff wrapper, structured logging, metrics counter
shim, env-driven config, error types, circuit breaker around the LLM call,
request-ID propagation, and a hash-chained JSONL audit writer.

NOT load-tested. NOT security-audited. Skeleton fidelity is "realistic shape" —
see ./README.md for the explicit caveats this file ships under.

Dependencies: httpx, openai, tenacity  (pip install httpx openai tenacity)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional, TypeVar

import httpx
from openai import OpenAI
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ---------------------------------------------------------------------------
# Benchmark declaration block — consumed by the harness
# ---------------------------------------------------------------------------

__benchmark_audit_checklist__: dict[str, bool] = {
    "event_hash_chain":   True,
    "per_step_inputs":    True,
    "per_step_outputs":   True,
    "adapter_args":       True,
    "approval_gates":     False,
    "config_snapshot":    True,
    "replayable":         False,
    "regulatory_grade":   False,
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

Severity = Literal["healthy", "degraded", "critical"]
T = TypeVar("T")


@dataclass(frozen=True)
class MonitorConfig:
    endpoint_url: str
    threshold_ms: float
    http_timeout_s: float = 10.0
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    cache_path: str = ".monitor_cache.json"
    audit_path: str = ".monitor_audit.jsonl"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_env(cls, *, endpoint_url: str, threshold_ms: float) -> "MonitorConfig":
        return cls(
            endpoint_url=endpoint_url,
            threshold_ms=threshold_ms,
            http_timeout_s=float(os.environ.get("MONITOR_HTTP_TIMEOUT_S", "10")),
            llm_model=os.environ.get("MONITOR_LLM_MODEL", "gpt-4o"),
            llm_temperature=float(os.environ.get("MONITOR_LLM_TEMPERATURE", "0.2")),
            cache_path=os.environ.get("MONITOR_CACHE_PATH", ".monitor_cache.json"),
            audit_path=os.environ.get("MONITOR_AUDIT_PATH", ".monitor_audit.jsonl"),
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class MonitorError(Exception):
    """Base exception for the monitor pipeline."""


class HealthCheckError(MonitorError):
    """HTTP probe failed beyond the retry budget."""


class LLMError(MonitorError):
    """LLM completion failed beyond the retry budget."""


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("monitor")
if not _LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}'
    ))
    _LOG.addHandler(handler)
    _LOG.setLevel(logging.INFO)


@dataclass
class MetricsShim:
    """Minimal in-process metrics counter; replace with Prometheus / OTEL in real deploys."""
    counters: Counter = field(default_factory=Counter)

    def incr(self, name: str, n: int = 1, **labels: str) -> None:
        key = name + "|" + ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        self.counters[key] += n


class CircuitBreaker:
    """Per-process circuit breaker — open after N consecutive failures."""

    def __init__(self, threshold: int = 3, cooldown_s: float = 60.0) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_s
        self._failures = 0
        self._opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at > self._cooldown:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record(self, ok: bool) -> None:
        if ok:
            self._failures = 0
            self._opened_at = None
            return
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = time.monotonic()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class FileCache:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        try:
            self._data: dict[str, str] = json.loads(self._path.read_text()) if self._path.exists() else {}
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._path.write_text(json.dumps(self._data, indent=2))


class HashChainAuditLog:
    """Hash-chained JSONL audit writer — each line links to the prior line's digest."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._last_hash = self._tail_hash()

    def _tail_hash(self) -> str:
        if not self._path.exists():
            return "GENESIS"
        try:
            tail = self._path.read_text(encoding="utf-8").strip().splitlines()
            return json.loads(tail[-1])["event_hash"] if tail else "GENESIS"
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
            return "GENESIS"

    def append(self, event: dict[str, Any]) -> str:
        payload = dict(event)
        payload["prev_hash"] = self._last_hash
        payload["ts_ns"] = time.time_ns()
        digest_input = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload["event_hash"] = hashlib.sha256(digest_input).hexdigest()
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
        self._last_hash = payload["event_hash"]
        return payload["event_hash"]


# ---------------------------------------------------------------------------
# Retry-wrapped network calls
# ---------------------------------------------------------------------------

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
)
def _probe_endpoint(cfg: MonitorConfig) -> tuple[Optional[int], float]:
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=cfg.http_timeout_s) as client:
            response = client.get(cfg.endpoint_url)
        latency_ms = (time.monotonic() - t0) * 1000.0
        return response.status_code, latency_ms
    except (httpx.ConnectError, httpx.TimeoutException):
        raise


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
)
def _llm_completion(client: OpenAI, prompt: str, max_tokens: int, cfg: MonitorConfig) -> str:
    completion = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=cfg.llm_temperature,
    )
    return completion.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MonitorResult:
    severity: Severity
    endpoint_url: str
    status_code: Optional[int]
    latency_ms: Optional[float]
    alert_text: Optional[str]
    request_id: str
    audit_head_hash: str


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def check_endpoint(
    cfg: MonitorConfig,
    *,
    cache: Optional[FileCache] = None,
    audit: Optional[HashChainAuditLog] = None,
    metrics: Optional[MetricsShim] = None,
    breaker: Optional[CircuitBreaker] = None,
    openai_client: Optional[OpenAI] = None,
) -> MonitorResult:
    cache = cache or FileCache(cfg.cache_path)
    audit = audit or HashChainAuditLog(cfg.audit_path)
    metrics = metrics or MetricsShim()
    breaker = breaker or CircuitBreaker()
    openai_client = openai_client or OpenAI()

    audit.append({"step": "config_snapshot", "request_id": cfg.request_id, "config": {
        "endpoint_url": cfg.endpoint_url,
        "threshold_ms": cfg.threshold_ms,
        "llm_model": cfg.llm_model,
    }})

    try:
        status_code, latency_ms = _probe_endpoint(cfg)
        is_up = status_code == 200
    except RetryError:
        status_code, latency_ms, is_up = None, None, False
    except (httpx.ConnectError, httpx.TimeoutException):
        status_code, latency_ms, is_up = None, None, False

    metrics.incr("monitor.probe", endpoint=cfg.endpoint_url, ok=str(is_up).lower())
    audit.append({
        "step": "probe", "request_id": cfg.request_id,
        "input": {"endpoint_url": cfg.endpoint_url, "threshold_ms": cfg.threshold_ms},
        "output": {"status_code": status_code, "latency_ms": latency_ms, "is_up": is_up},
    })

    if not is_up:
        severity: Severity = "critical"
    elif latency_ms is not None and latency_ms > cfg.threshold_ms:
        severity = "degraded"
    else:
        severity = "healthy"

    alert_text: Optional[str] = None
    if severity != "healthy":
        if not breaker.allow():
            _LOG.warning("circuit_open severity=%s skipping_llm", severity)
            metrics.incr("monitor.llm.skipped", severity=severity)
        else:
            prompt = _alert_prompt(cfg.endpoint_url, severity, status_code, latency_ms, cfg.threshold_ms)
            try:
                alert_text = _llm_completion(openai_client, prompt, 200 if severity == "critical" else 150, cfg)
                breaker.record(ok=True)
                metrics.incr("monitor.llm.ok", severity=severity)
            except Exception as exc:
                breaker.record(ok=False)
                metrics.incr("monitor.llm.fail", severity=severity)
                _LOG.error("llm_error %s severity=%s", type(exc).__name__, severity)
                raise LLMError(f"LLM completion failed: {exc!r}") from exc
            audit.append({
                "step": "alert", "request_id": cfg.request_id,
                "input": {"prompt_chars": len(prompt), "severity": severity},
                "output": {"alert_chars": len(alert_text)},
            })

    cache.set("monitor_last_severity", severity)
    if alert_text is not None:
        cache.set("monitor_last_alert", alert_text)

    head_hash = audit.append({
        "step": "complete", "request_id": cfg.request_id,
        "output": {"severity": severity, "status_code": status_code, "latency_ms": latency_ms},
    })

    return MonitorResult(
        severity=severity,
        endpoint_url=cfg.endpoint_url,
        status_code=status_code,
        latency_ms=latency_ms,
        alert_text=alert_text,
        request_id=cfg.request_id,
        audit_head_hash=head_hash,
    )


def _alert_prompt(
    endpoint_url: str, severity: Severity, status_code: Optional[int],
    latency_ms: Optional[float], threshold_ms: float,
) -> str:
    if severity == "critical":
        return (
            f"Critical: endpoint {endpoint_url} is DOWN. "
            f"HTTP status: {status_code}. Draft a concise ops incident alert."
        )
    return (
        f"Degraded: endpoint {endpoint_url} latency {latency_ms:.0f}ms "
        f"exceeds threshold {threshold_ms:.0f}ms. Draft a concise ops alert."
    )


if __name__ == "__main__":
    import sys
    cfg = MonitorConfig.from_env(
        endpoint_url=sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/status/200",
        threshold_ms=float(sys.argv[2]) if len(sys.argv) > 2 else 500.0,
    )
    result = check_endpoint(cfg)
    print(json.dumps(vars(result), indent=2, default=str))
