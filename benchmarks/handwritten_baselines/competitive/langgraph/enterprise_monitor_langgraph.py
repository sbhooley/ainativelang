#!/usr/bin/env python3
"""
LangGraph-shaped baseline for enterprise_monitor.ainl.

Semantically aligned with:
  - examples/benchmark/enterprise_monitor.ainl
  - benchmarks/handwritten_baselines/authoring_density/enterprise_monitor.py

Represents what a proficient team builds with LangGraph when asked for a
health monitor with LLM alerts on incident — including graph boilerplate,
state schema, and conditional routing nodes.

Install: pip install langgraph httpx openai
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, TypedDict

import httpx
from openai import OpenAI

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "langgraph is required for this baseline. Install with: pip install langgraph"
    ) from e

Severity = Literal["healthy", "degraded", "critical"]


@dataclass
class MonitorResult:
    severity: Severity
    endpoint_url: str
    status_code: Optional[int]
    latency_ms: Optional[float]
    alert_text: Optional[str]


class MonitorState(TypedDict, total=False):
    endpoint_url: str
    threshold_ms: float
    http_timeout: float
    status_code: Optional[int]
    latency_ms: Optional[float]
    is_up: bool
    severity: Severity
    alert_text: Optional[str]
    openai_client: OpenAI


def node_poll_http(state: MonitorState) -> dict:
    endpoint_url = state["endpoint_url"]
    http_timeout = state.get("http_timeout", 10.0)
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=http_timeout) as client:
            response = client.get(endpoint_url)
        latency_ms = (time.monotonic() - t0) * 1000.0
        status_code: Optional[int] = response.status_code
        is_up = status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        latency_ms = (time.monotonic() - t0) * 1000.0
        status_code = None
        is_up = False
    return {
        "status_code": status_code,
        "latency_ms": latency_ms,
        "is_up": is_up,
    }


def node_route_severity(state: MonitorState) -> dict:
    if not state.get("is_up"):
        severity: Severity = "critical"
    elif (state.get("latency_ms") or 0) > state["threshold_ms"]:
        severity = "degraded"
    else:
        severity = "healthy"
    return {"severity": severity}


def node_alert_critical(state: MonitorState) -> dict:
    client = state.get("openai_client") or OpenAI()
    endpoint_url = state["endpoint_url"]
    status_code = state.get("status_code")
    prompt = (
        f"Critical: endpoint {endpoint_url} is DOWN. "
        f"HTTP status: {status_code}. "
        "Draft a concise ops incident alert."
    )
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.2,
    )
    alert_text = completion.choices[0].message.content or ""
    return {"alert_text": alert_text}


def node_alert_degraded(state: MonitorState) -> dict:
    client = state.get("openai_client") or OpenAI()
    endpoint_url = state["endpoint_url"]
    latency_ms = state.get("latency_ms") or 0.0
    threshold_ms = state["threshold_ms"]
    prompt = (
        f"Degraded: endpoint {endpoint_url} latency {latency_ms:.0f}ms "
        f"exceeds threshold {threshold_ms:.0f}ms. "
        "Draft a concise ops alert."
    )
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3,
    )
    alert_text = completion.choices[0].message.content or ""
    return {"alert_text": alert_text}


def node_healthy_result(state: MonitorState) -> dict:
    latency_ms = state.get("latency_ms") or 0.0
    return {"alert_text": f"healthy: {latency_ms:.0f}ms"}


def _route_after_poll(state: MonitorState) -> str:
    if not state.get("is_up"):
        return "critical"
    if (state.get("latency_ms") or 0) > state["threshold_ms"]:
        return "degraded"
    return "healthy"


def build_enterprise_monitor_graph():
    g = StateGraph(MonitorState)
    g.add_node("poll_http", node_poll_http)
    g.add_node("route_severity", node_route_severity)
    g.add_node("alert_critical", node_alert_critical)
    g.add_node("alert_degraded", node_alert_degraded)
    g.add_node("healthy", node_healthy_result)
    g.add_edge(START, "poll_http")
    g.add_edge("poll_http", "route_severity")
    g.add_conditional_edges(
        "route_severity",
        _route_after_poll,
        {
            "critical": "alert_critical",
            "degraded": "alert_degraded",
            "healthy": "healthy",
        },
    )
    g.add_edge("alert_critical", END)
    g.add_edge("alert_degraded", END)
    g.add_edge("healthy", END)
    return g.compile()


def run_enterprise_monitor_langgraph(
    endpoint_url: str,
    threshold_ms: float = 500.0,
    *,
    openai_client: Optional[OpenAI] = None,
) -> MonitorResult:
    app = build_enterprise_monitor_graph()
    final = app.invoke(
        {
            "endpoint_url": endpoint_url,
            "threshold_ms": threshold_ms,
            "openai_client": openai_client or OpenAI(),
        }
    )
    severity = final.get("severity") or "healthy"
    return MonitorResult(
        severity=severity,  # type: ignore[arg-type]
        endpoint_url=endpoint_url,
        status_code=final.get("status_code"),
        latency_ms=final.get("latency_ms"),
        alert_text=final.get("alert_text"),
    )


def source_text_for_token_count() -> str:
    """Return this module source for tiktoken authoring-size comparison."""
    return Path(__file__).read_text(encoding="utf-8")


if __name__ == "__main__":
    _ROOT = Path(__file__).resolve().parents[3]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/status/200"
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 500.0
    result = run_enterprise_monitor_langgraph(endpoint, threshold)
    print(json.dumps(vars(result), indent=2))
