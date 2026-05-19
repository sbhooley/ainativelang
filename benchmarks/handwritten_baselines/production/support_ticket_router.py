"""
Production-grade baseline-B implementation: customer support ticket router —
semantically equivalent to examples/workflows/support_ticket_router.ainl.

Adds typed retry/backoff, structured logging, metrics shim, env-driven config,
explicit error types, a circuit breaker on the LLM, request-ID propagation,
PII redaction on logged ticket text, and a hash-chained JSONL audit log.

NOT load-tested. NOT security-audited. See ./README.md for the explicit
caveats this file ships under.

Dependencies: openai, tenacity  (pip install openai tenacity)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from openai import OpenAI
from tenacity import (
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


Priority = Literal["critical", "high", "normal", "low"]
Category = Literal["bug", "billing", "feature", "general"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RouterConfig:
    llm_model: str = "gpt-4o"
    classify_temperature: float = 0.0
    draft_temperature: float = 0.5
    audit_path: str = ".router_audit.jsonl"
    redact_pii_in_logs: bool = True
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_env(cls) -> "RouterConfig":
        return cls(
            llm_model=os.environ.get("ROUTER_LLM_MODEL", "gpt-4o"),
            classify_temperature=float(os.environ.get("ROUTER_CLASSIFY_TEMP", "0.0")),
            draft_temperature=float(os.environ.get("ROUTER_DRAFT_TEMP", "0.5")),
            audit_path=os.environ.get("ROUTER_AUDIT_PATH", ".router_audit.jsonl"),
            redact_pii_in_logs=os.environ.get("ROUTER_REDACT_PII", "1") == "1",
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class RouterError(Exception):
    """Base exception for the router pipeline."""


class ClassificationError(RouterError):
    """LLM classification failed beyond the retry budget."""


class DraftError(RouterError):
    """LLM draft response failed beyond the retry budget."""


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("router")
if not _LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}'
    ))
    _LOG.addHandler(handler)
    _LOG.setLevel(logging.INFO)


@dataclass
class MetricsShim:
    counters: Counter = field(default_factory=Counter)

    def incr(self, name: str, n: int = 1, **labels: str) -> None:
        key = name + "|" + ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        self.counters[key] += n


class CircuitBreaker:
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
# PII redaction (logs only; LLM input is unredacted because classification
# requires the original wording)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("<email>", text)
    text = _PHONE_RE.sub("<phone>", text)
    return text


# ---------------------------------------------------------------------------
# Hash-chained audit log
# ---------------------------------------------------------------------------

class HashChainAuditLog:
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
# Routing tables (deterministic — zero LLM tokens)
# ---------------------------------------------------------------------------

TEAM_TABLE: dict[tuple[Priority, Category], tuple[str, int]] = {
    ("critical", "billing"):  ("billing-escalations", 2),
    ("critical", "bug"):      ("engineering-oncall",  1),
    ("critical", "feature"):  ("engineering-oncall",  1),
    ("critical", "general"):  ("engineering-oncall",  1),
    ("high",     "billing"):  ("billing",             4),
    ("high",     "bug"):      ("support-tier2",       8),
    ("high",     "feature"):  ("support-tier2",       8),
    ("high",     "general"):  ("support-tier2",       8),
}

DRAFT_INSTRUCTIONS: dict[tuple[Priority, Category], str] = {
    ("critical", "billing"): (
        "Write an empathetic urgent response for this critical billing issue. "
        "State a 2-hour SLA and offer a direct callback."
    ),
    ("critical", "bug"): (
        "Write an empathetic urgent acknowledgment for this critical engineering issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "feature"): (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "general"): (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("high", "billing"): (
        "Write a professional response for this high-priority billing enquiry. "
        "Confirm 4-hour SLA and name the billing team as the owner."
    ),
    ("high", "bug"): (
        "Write a professional response for this high-priority support ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "feature"): (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "general"): (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
}

NORMAL_DRAFT = (
    "Write a friendly, helpful first response for this support ticket. "
    "Confirm 24-hour SLA."
)


# ---------------------------------------------------------------------------
# Retry-wrapped LLM calls
# ---------------------------------------------------------------------------

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
)
def _classify(client: OpenAI, instruction: str, ticket_text: str, cfg: RouterConfig) -> str:
    completion = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": f"{instruction} Ticket: {ticket_text}"}],
        max_tokens=10,
        temperature=cfg.classify_temperature,
    )
    return (completion.choices[0].message.content or "").strip().lower()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
)
def _draft(client: OpenAI, instruction: str, ticket_text: str, cfg: RouterConfig, max_tokens: int) -> str:
    completion = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": f"{instruction} Ticket: {ticket_text}"}],
        max_tokens=max_tokens,
        temperature=cfg.draft_temperature,
    )
    return completion.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TicketRouteResult:
    ticket_id: str
    priority: Priority
    category: Category
    team: str
    sla_hours: int
    draft_response: str
    request_id: str
    audit_head_hash: str


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def route_ticket(
    ticket_id: str,
    ticket_text: str,
    cfg: Optional[RouterConfig] = None,
    *,
    audit: Optional[HashChainAuditLog] = None,
    metrics: Optional[MetricsShim] = None,
    breaker: Optional[CircuitBreaker] = None,
    openai_client: Optional[OpenAI] = None,
) -> TicketRouteResult:
    cfg = cfg or RouterConfig.from_env()
    audit = audit or HashChainAuditLog(cfg.audit_path)
    metrics = metrics or MetricsShim()
    breaker = breaker or CircuitBreaker()
    openai_client = openai_client or OpenAI()

    logged_text = _redact(ticket_text) if cfg.redact_pii_in_logs else ticket_text

    audit.append({"step": "config_snapshot", "request_id": cfg.request_id, "ticket_id": ticket_id, "config": {
        "llm_model": cfg.llm_model,
        "classify_temperature": cfg.classify_temperature,
        "draft_temperature": cfg.draft_temperature,
    }})

    if not breaker.allow():
        _LOG.warning("circuit_open ticket_id=%s skipping_llm", ticket_id)
        metrics.incr("router.skipped", ticket_id=ticket_id)
        raise ClassificationError("LLM circuit breaker open")

    try:
        priority_raw = _classify(
            openai_client,
            "Classify this support ticket priority as exactly one word — critical, high, normal, or low.",
            ticket_text, cfg,
        )
        category_raw = _classify(
            openai_client,
            "Classify this support ticket category as exactly one word — bug, billing, feature, or general.",
            ticket_text, cfg,
        )
        breaker.record(ok=True)
    except Exception as exc:
        breaker.record(ok=False)
        metrics.incr("router.classify.fail", ticket_id=ticket_id)
        _LOG.error("classify_error %s ticket_id=%s text=%s", type(exc).__name__, ticket_id, logged_text[:80])
        raise ClassificationError(f"classification failed: {exc!r}") from exc

    priority: Priority = priority_raw if priority_raw in ("critical", "high", "normal", "low") else "normal"  # type: ignore[assignment]
    category: Category = category_raw if category_raw in ("bug", "billing", "feature", "general") else "general"  # type: ignore[assignment]

    metrics.incr("router.classified", priority=priority, category=category)
    audit.append({
        "step": "classify", "request_id": cfg.request_id, "ticket_id": ticket_id,
        "input": {"ticket_chars": len(ticket_text)},
        "output": {"priority": priority, "category": category},
    })

    route_key = (priority, category)
    if route_key in TEAM_TABLE:
        team, sla_hours = TEAM_TABLE[route_key]
        draft_instruction = DRAFT_INSTRUCTIONS[route_key]
        max_tokens = 200 if priority == "critical" else 180
    else:
        team, sla_hours, draft_instruction, max_tokens = "support-tier1", 24, NORMAL_DRAFT, 150

    try:
        draft = _draft(openai_client, draft_instruction, ticket_text, cfg, max_tokens)
        breaker.record(ok=True)
        metrics.incr("router.draft.ok", priority=priority, category=category)
    except Exception as exc:
        breaker.record(ok=False)
        metrics.incr("router.draft.fail", priority=priority, category=category)
        _LOG.error("draft_error %s ticket_id=%s", type(exc).__name__, ticket_id)
        raise DraftError(f"draft failed: {exc!r}") from exc

    head_hash = audit.append({
        "step": "complete", "request_id": cfg.request_id, "ticket_id": ticket_id,
        "input": {"team": team, "sla_hours": sla_hours, "max_tokens": max_tokens},
        "output": {"draft_chars": len(draft)},
    })

    return TicketRouteResult(
        ticket_id=ticket_id,
        priority=priority,
        category=category,
        team=team,
        sla_hours=sla_hours,
        draft_response=draft,
        request_id=cfg.request_id,
        audit_head_hash=head_hash,
    )


if __name__ == "__main__":
    import sys

    ticket_id = sys.argv[1] if len(sys.argv) > 1 else "TKT-0001"
    ticket_text = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "I was charged twice for my subscription this month and need an immediate refund."
    )
    result = route_ticket(ticket_id, ticket_text)
    print(json.dumps(vars(result), indent=2))
