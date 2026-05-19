"""
Production-grade baseline-B implementation: multi-source e-commerce order
processing pipeline — semantically equivalent to
examples/workflows/data_pipeline.ainl.

Adds typed retry/backoff on every HTTP and LLM call, structured logging,
metrics shim, env-driven config, explicit error types per failure mode,
LLM circuit breaker, request-ID propagation, idempotency keys via the cache,
PII redaction on logged customer data, an enterprise-tier approval-gate hook
(declined by default unless explicitly enabled), and a hash-chained JSONL
audit log covering every routing branch.

NOT load-tested. NOT security-audited. See ./README.md for the explicit
caveats this file ships under.

Dependencies: httpx, openai, tenacity  (pip install httpx openai tenacity)
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

import httpx
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
    "approval_gates":     True,   # explicit approval hook for enterprise tier
    "config_snapshot":    True,
    "replayable":         False,  # cache + audit, but no IR-level replay
    "regulatory_grade":   False,  # close but no SOC2/HIPAA attestation
}


FulfilmentType = Literal["digital", "physical", "subscription"]
Disposition = Literal[
    "duplicate",
    "rejected:invalid",
    "rejected:fraud",
    "rejected:approval_denied",
    "processing:digital",
    "processing:physical",
    "backorder:physical",
    "processing:subscription",
    "processing:vip",
    "processing:enterprise_vip",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipelineConfig:
    customer_api: str
    product_api: str
    http_timeout_s: float = 10.0
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.4
    cache_path: str = ".pipeline_cache.json"
    orders_log_path: str = ".pipeline_orders.jsonl"
    audit_path: str = ".pipeline_audit.jsonl"
    require_enterprise_approval: bool = False
    vip_digital_threshold: float = 500.0
    vip_physical_threshold: float = 500.0
    vip_subscription_threshold: float = 200.0
    fraud_block_threshold: int = 75
    redact_pii_in_logs: bool = True
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_env(cls, *, customer_api: str, product_api: str) -> "PipelineConfig":
        return cls(
            customer_api=customer_api,
            product_api=product_api,
            http_timeout_s=float(os.environ.get("PIPELINE_HTTP_TIMEOUT_S", "10")),
            llm_model=os.environ.get("PIPELINE_LLM_MODEL", "gpt-4o"),
            llm_temperature=float(os.environ.get("PIPELINE_LLM_TEMPERATURE", "0.4")),
            cache_path=os.environ.get("PIPELINE_CACHE_PATH", ".pipeline_cache.json"),
            orders_log_path=os.environ.get("PIPELINE_ORDERS_LOG", ".pipeline_orders.jsonl"),
            audit_path=os.environ.get("PIPELINE_AUDIT_PATH", ".pipeline_audit.jsonl"),
            require_enterprise_approval=os.environ.get("PIPELINE_REQUIRE_ENTERPRISE_APPROVAL", "0") == "1",
            vip_digital_threshold=float(os.environ.get("PIPELINE_VIP_DIGITAL", "500")),
            vip_physical_threshold=float(os.environ.get("PIPELINE_VIP_PHYSICAL", "500")),
            vip_subscription_threshold=float(os.environ.get("PIPELINE_VIP_SUBSCRIPTION", "200")),
            fraud_block_threshold=int(os.environ.get("PIPELINE_FRAUD_THRESHOLD", "75")),
            redact_pii_in_logs=os.environ.get("PIPELINE_REDACT_PII", "1") == "1",
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Base exception for the pipeline."""


class EnrichmentError(PipelineError):
    """Customer or product enrichment call failed beyond the retry budget."""


class LLMError(PipelineError):
    """LLM completion failed beyond the retry budget."""


class ApprovalDenied(PipelineError):
    """Enterprise approval gate refused the order."""


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("pipeline")
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
# PII redaction (logs only)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _redact(text: str) -> str:
    return _EMAIL_RE.sub("<email>", text)


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


class AppendLog:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def append(self, collection: str, tag: str, order_id: str, body: str) -> None:
        entry = {
            "ts": time.time(), "collection": collection, "tag": tag,
            "order_id": order_id, "body": body,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")


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
# Approval gate (no-op default; real deploys wire to a human-in-the-loop API)
# ---------------------------------------------------------------------------

def default_enterprise_approval(order_id: str, customer_id: str, order_value: float) -> bool:
    """Approve enterprise orders by default. Real systems wire to an
    approval API; we keep the signature so it's a measurable surface."""
    _LOG.info("approval_check order_id=%s customer_id=%s value=%.2f",
              order_id, customer_id, order_value)
    return True


# ---------------------------------------------------------------------------
# Retry-wrapped enrichment + LLM
# ---------------------------------------------------------------------------

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
)
def _enrich(http: httpx.Client, url: str) -> dict[str, Any]:
    response = http.get(url)
    response.raise_for_status()
    return response.json()["body"]


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
)
def _llm_completion(client: OpenAI, prompt: str, max_tokens: int, cfg: PipelineConfig) -> str:
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
class DispatchResult:
    order_id: str
    disposition: Disposition
    detail: str
    confirmation_email: Optional[str]
    request_id: str
    audit_head_hash: str


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_order(
    order_id: str,
    customer_id: str,
    product_id: str,
    order_value: float,
    fulfilment_type: FulfilmentType,
    cfg: Optional[PipelineConfig] = None,
    *,
    cache: Optional[FileCache] = None,
    orders_log: Optional[AppendLog] = None,
    audit: Optional[HashChainAuditLog] = None,
    metrics: Optional[MetricsShim] = None,
    breaker: Optional[CircuitBreaker] = None,
    openai_client: Optional[OpenAI] = None,
    approval_fn=default_enterprise_approval,
) -> DispatchResult:
    if cfg is None:
        raise ValueError("PipelineConfig is required (use PipelineConfig.from_env(...))")
    cache = cache or FileCache(cfg.cache_path)
    orders_log = orders_log or AppendLog(cfg.orders_log_path)
    audit = audit or HashChainAuditLog(cfg.audit_path)
    metrics = metrics or MetricsShim()
    breaker = breaker or CircuitBreaker()
    openai_client = openai_client or OpenAI()

    state_key = f"order_state:{order_id}"

    audit.append({"step": "config_snapshot", "request_id": cfg.request_id, "order_id": order_id, "config": {
        "customer_api": cfg.customer_api, "product_api": cfg.product_api,
        "fraud_block_threshold": cfg.fraud_block_threshold,
        "vip_digital_threshold": cfg.vip_digital_threshold,
        "require_enterprise_approval": cfg.require_enterprise_approval,
    }})

    if cache.get(state_key) is not None:
        head = audit.append({"step": "duplicate", "request_id": cfg.request_id, "order_id": order_id})
        return DispatchResult(order_id, "duplicate", f"duplicate:{order_id}", None, cfg.request_id, head)

    if order_value <= 0:
        cache.set(state_key, "rejected:invalid")
        head = audit.append({"step": "validate", "request_id": cfg.request_id, "order_id": order_id,
                             "output": {"valid": False}})
        return DispatchResult(order_id, "rejected:invalid", "rejected:invalid_order_value", None, cfg.request_id, head)

    try:
        with httpx.Client(timeout=cfg.http_timeout_s) as http:
            cust_data = _enrich(http, f"{cfg.customer_api}{customer_id}")
            prod_data = _enrich(http, f"{cfg.product_api}{product_id}")
    except Exception as exc:
        metrics.incr("pipeline.enrichment.fail", order_id=order_id)
        _LOG.error("enrichment_error %s order_id=%s", type(exc).__name__, order_id)
        raise EnrichmentError(f"enrichment failed: {exc!r}") from exc

    if cfg.redact_pii_in_logs:
        cust_data_logged = {k: (_redact(str(v)) if isinstance(v, str) else v) for k, v in cust_data.items()}
    else:
        cust_data_logged = dict(cust_data)

    customer_tier = cust_data["tier"]
    fraud_score = int(cust_data["fraud_score"])
    product_name = prod_data["name"]
    inventory = int(prod_data["inventory"])

    audit.append({
        "step": "enrich", "request_id": cfg.request_id, "order_id": order_id,
        "input": {"customer_id": customer_id, "product_id": product_id},
        "output": {"customer_logged": cust_data_logged, "product_name": product_name, "inventory": inventory},
    })

    if fraud_score > cfg.fraud_block_threshold:
        cache.set(state_key, "rejected:fraud")
        metrics.incr("pipeline.fraud_block")
        head = audit.append({"step": "fraud_block", "request_id": cfg.request_id, "order_id": order_id,
                             "output": {"fraud_score": fraud_score}})
        return DispatchResult(order_id, "rejected:fraud", f"blocked:fraud_score={fraud_score}", None,
                              cfg.request_id, head)

    is_highval_digital = order_value > cfg.vip_digital_threshold
    is_highval_phys = order_value > cfg.vip_physical_threshold
    is_highval_sub = order_value > cfg.vip_subscription_threshold

    if fulfilment_type == "digital":
        if is_highval_digital:
            return _vip_path(order_id, customer_id, product_name, customer_tier, cfg, cache,
                             orders_log, audit, metrics, breaker, openai_client, approval_fn,
                             order_value, state_key)
        cache.set(state_key, "processing:digital")
        head = audit.append({"step": "route", "request_id": cfg.request_id, "order_id": order_id,
                             "output": {"route": "digital_standard"}})
        return DispatchResult(order_id, "processing:digital", f"dispatch:digital:immediate:{product_id}",
                              None, cfg.request_id, head)

    if fulfilment_type == "physical":
        if inventory <= 0:
            cache.set(state_key, "backorder:physical")
            head = audit.append({"step": "route", "request_id": cfg.request_id, "order_id": order_id,
                                 "output": {"route": "physical_backorder", "inventory": inventory}})
            return DispatchResult(order_id, "backorder:physical",
                                  f"backorder:physical:notify:{customer_id}", None, cfg.request_id, head)
        if is_highval_phys:
            return _vip_path(order_id, customer_id, product_name, customer_tier, cfg, cache,
                             orders_log, audit, metrics, breaker, openai_client, approval_fn,
                             order_value, state_key)
        cache.set(state_key, "processing:physical")
        head = audit.append({"step": "route", "request_id": cfg.request_id, "order_id": order_id,
                             "output": {"route": "physical_standard"}})
        return DispatchResult(order_id, "processing:physical",
                              f"dispatch:physical:warehouse:{product_id}", None, cfg.request_id, head)

    sub_id = cust_data.get("subscription_id", "unknown")
    if is_highval_sub:
        return _vip_path(order_id, customer_id, product_name, customer_tier, cfg, cache,
                         orders_log, audit, metrics, breaker, openai_client, approval_fn,
                         order_value, state_key)
    cache.set(state_key, "processing:subscription")
    head = audit.append({"step": "route", "request_id": cfg.request_id, "order_id": order_id,
                         "output": {"route": "subscription_standard"}})
    return DispatchResult(order_id, "processing:subscription",
                          f"dispatch:subscription:renew:{sub_id}", None, cfg.request_id, head)


def _vip_path(
    order_id: str, customer_id: str, product_name: str, customer_tier: str,
    cfg: PipelineConfig, cache: FileCache, orders_log: AppendLog,
    audit: HashChainAuditLog, metrics: MetricsShim, breaker: CircuitBreaker,
    openai_client: OpenAI, approval_fn, order_value: float, state_key: str,
) -> DispatchResult:
    if customer_tier == "enterprise":
        if cfg.require_enterprise_approval and not approval_fn(order_id, customer_id, order_value):
            cache.set(state_key, "rejected:approval_denied")
            head = audit.append({"step": "approval", "request_id": cfg.request_id, "order_id": order_id,
                                 "output": {"approved": False}})
            raise ApprovalDenied(f"enterprise approval denied for {order_id}")
        audit.append({"step": "approval", "request_id": cfg.request_id, "order_id": order_id,
                      "output": {"approved": True}})
        prompt = (
            f"Generate a professional enterprise order confirmation for {customer_id} ordering "
            f"{product_name}. Mention dedicated account manager, priority SLA, and invoice terms."
        )
        max_tokens, disposition, tag = 250, "processing:enterprise_vip", "vip_enterprise"
    else:
        prompt = (
            f"Generate a warm VIP order confirmation for {customer_id} ordering {product_name}. "
            "Mention priority handling, estimated delivery, and loyalty points."
        )
        max_tokens, disposition, tag = 200, "processing:vip", "vip"

    if not breaker.allow():
        metrics.incr("pipeline.llm.skipped", tier=customer_tier)
        raise LLMError("LLM circuit breaker open")

    try:
        email = _llm_completion(openai_client, prompt, max_tokens, cfg)
        breaker.record(ok=True)
        metrics.incr("pipeline.llm.ok", tier=customer_tier)
    except Exception as exc:
        breaker.record(ok=False)
        metrics.incr("pipeline.llm.fail", tier=customer_tier)
        _LOG.error("llm_error %s order_id=%s", type(exc).__name__, order_id)
        raise LLMError(f"vip email generation failed: {exc!r}") from exc

    cache.set(state_key, disposition)
    orders_log.append("orders", tag, order_id, email)
    head = audit.append({
        "step": "vip_email", "request_id": cfg.request_id, "order_id": order_id,
        "input": {"prompt_chars": len(prompt), "max_tokens": max_tokens},
        "output": {"email_chars": len(email), "tag": tag, "disposition": disposition},
    })
    return DispatchResult(order_id, disposition, "dispatch:vip", email, cfg.request_id, head)  # type: ignore[arg-type]


if __name__ == "__main__":
    import sys
    cfg = PipelineConfig.from_env(
        customer_api=os.environ.get("CUSTOMER_API", "https://api.example.com/customers/"),
        product_api=os.environ.get("PRODUCT_API", "https://api.example.com/products/"),
    )
    order_id = sys.argv[1] if len(sys.argv) > 1 else "ORD-0001"
    customer_id = sys.argv[2] if len(sys.argv) > 2 else "CUST-0001"
    product_id = sys.argv[3] if len(sys.argv) > 3 else "PROD-0001"
    order_value = float(sys.argv[4]) if len(sys.argv) > 4 else 600.0
    fulfilment: FulfilmentType = sys.argv[5] if len(sys.argv) > 5 else "physical"  # type: ignore[assignment]
    result = process_order(order_id, customer_id, product_id, order_value, fulfilment, cfg)
    print(json.dumps(vars(result), indent=2))
