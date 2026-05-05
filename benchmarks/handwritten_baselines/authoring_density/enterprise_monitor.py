"""
Authoring-density baseline: enterprise infrastructure health monitor — idiomatic Python.

Semantically equivalent to examples/benchmark/enterprise_monitor.ainl.
Written in the style a proficient Python developer (or LLM) would produce
when asked to "build a health monitor that polls an HTTP endpoint, routes
by severity, generates LLM incident alerts only when needed, and caches state."

Dependencies: httpx, openai  (pip install httpx openai)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import httpx
from openai import OpenAI


Severity = Literal["healthy", "degraded", "critical"]


# ---------------------------------------------------------------------------
# Simple file-backed cache (mirrors cache adapter behaviour)
# ---------------------------------------------------------------------------

class FileCache:
    """Persistent JSON key-value store backed by a local file."""

    def __init__(self, path: str = ".monitor_cache.json") -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._path.write_text(json.dumps(self._data, indent=2))


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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def check_endpoint(
    endpoint_url: str,
    threshold_ms: float,
    cache: Optional[FileCache] = None,
    openai_client: Optional[OpenAI] = None,
    http_timeout: float = 10.0,
) -> MonitorResult:
    """
    Poll endpoint, evaluate status + latency, route by severity, generate
    LLM alert only when degraded or down, cache severity state.
    """
    if cache is None:
        cache = FileCache()
    if openai_client is None:
        openai_client = OpenAI()

    # Poll the health endpoint
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=http_timeout) as client:
            response = client.get(endpoint_url)
        latency_ms = (time.monotonic() - t0) * 1000.0
        status_code: Optional[int] = response.status_code
        is_up = (status_code == 200)
    except (httpx.ConnectError, httpx.TimeoutException):
        latency_ms = (time.monotonic() - t0) * 1000.0
        status_code = None
        is_up = False

    # Routing — zero LLM tokens
    if not is_up:
        severity: Severity = "critical"
    elif latency_ms > threshold_ms:
        severity = "degraded"
    else:
        severity = "healthy"

    # LLM alert generation — only for non-healthy states
    alert_text: Optional[str] = None

    if severity == "critical":
        prompt = (
            f"Critical: endpoint {endpoint_url} is DOWN. "
            f"HTTP status: {status_code}. "
            "Draft a concise ops incident alert."
        )
        completion = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        alert_text = completion.choices[0].message.content or ""

    elif severity == "degraded":
        prompt = (
            f"Degraded: endpoint {endpoint_url} latency {latency_ms:.0f}ms "
            f"exceeds threshold {threshold_ms:.0f}ms. "
            "Draft a concise ops alert."
        )
        completion = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        alert_text = completion.choices[0].message.content or ""

    # Cache severity state
    cache.set("monitor_last_severity", severity)
    if alert_text is not None:
        cache.set("monitor_last_alert", alert_text)

    return MonitorResult(
        severity=severity,
        endpoint_url=endpoint_url,
        status_code=status_code,
        latency_ms=latency_ms,
        alert_text=alert_text,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    endpoint_url = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/status/200"
    threshold_ms = float(sys.argv[2]) if len(sys.argv) > 2 else 500.0
    result = check_endpoint(endpoint_url, threshold_ms)
    print(json.dumps(vars(result), indent=2))
