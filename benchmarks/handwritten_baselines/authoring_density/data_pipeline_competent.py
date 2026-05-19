"""
Authoring-density baseline: multi-source e-commerce order processing pipeline —
idiomatic hand-crafted Python (NOT LLM-generated).

Semantically equivalent to examples/workflows/data_pipeline.ainl.

This is the "competent_python" baseline-B variant: what a proficient Python
developer writes in an afternoon when handed the same spec. It is the fair
counterpoint to data_pipeline_llm_generated.py (which is intentionally
verbose / defensive / annotated, matching LLM authoring style).

Compared to the LLM-generated variant this file:
  - Skips defensive type narrowing the original spec doesn't require.
  - Uses a single FileCache class instead of per-state classes.
  - Keeps inline routing instead of dispatch tables.
  - Is ~1/3 the source size while preserving all 8 routing branches and
    both LLM gates from the AINL source.

This is the version used as baseline B in
scripts/benchmark_vs_hand_runner.py — see also docs/competitive/
VS_HAND_WRITTEN_RUNNER.md.

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


FulfilmentType = Literal["digital", "physical", "subscription"]
Disposition = Literal[
    "duplicate",
    "rejected:invalid",
    "rejected:fraud",
    "processing:digital",
    "processing:physical",
    "backorder:physical",
    "processing:subscription",
    "processing:vip",
    "processing:enterprise_vip",
]


@dataclass
class DispatchResult:
    order_id: str
    disposition: Disposition
    detail: str
    confirmation_email: Optional[str]


class FileCache:
    """Persistent JSON KV store mirroring the AINL cache adapter."""

    def __init__(self, path: str = ".pipeline_cache.json") -> None:
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
    """Append-only audit log mirroring memory.APPEND in the AINL source."""

    def __init__(self, path: str = ".pipeline_orders.jsonl") -> None:
        self._path = Path(path)

    def append(self, collection: str, tag: str, order_id: str, body: str) -> None:
        entry = {
            "ts": time.time(),
            "collection": collection,
            "tag": tag,
            "order_id": order_id,
            "body": body,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")


def process_order(
    order_id: str,
    customer_id: str,
    product_id: str,
    order_value: float,
    fulfilment_type: FulfilmentType,
    customer_api: str,
    product_api: str,
    cache: Optional[FileCache] = None,
    orders_log: Optional[AppendLog] = None,
    openai_client: Optional[OpenAI] = None,
    http_timeout: float = 10.0,
) -> DispatchResult:
    """Process an order through validation, enrichment, fraud check, and routing."""
    cache = cache or FileCache()
    orders_log = orders_log or AppendLog()
    openai_client = openai_client or OpenAI()

    state_key = f"order_state:{order_id}"

    if cache.get(state_key) is not None:
        return DispatchResult(order_id, "duplicate", f"duplicate:{order_id}", None)

    if order_value <= 0:
        cache.set(state_key, "rejected:invalid")
        return DispatchResult(order_id, "rejected:invalid", "rejected:invalid_order_value", None)

    with httpx.Client(timeout=http_timeout) as http:
        cust_resp = http.get(f"{customer_api}{customer_id}")
        cust_data = cust_resp.json()["body"]
        prod_resp = http.get(f"{product_api}{product_id}")
        prod_data = prod_resp.json()["body"]

    customer_tier = cust_data["tier"]
    fraud_score = int(cust_data["fraud_score"])
    product_name = prod_data["name"]
    inventory = int(prod_data["inventory"])

    if fraud_score > 75:
        cache.set(state_key, "rejected:fraud")
        return DispatchResult(
            order_id,
            "rejected:fraud",
            f"blocked:fraud_score={fraud_score}",
            None,
        )

    is_highval_digital = order_value > 500
    is_highval_phys = order_value > 500
    is_highval_sub = order_value > 200

    if fulfilment_type == "digital":
        if is_highval_digital:
            return _vip_path(order_id, customer_id, product_name, customer_tier, cache, orders_log, openai_client, state_key)
        cache.set(state_key, "processing:digital")
        return DispatchResult(order_id, "processing:digital", f"dispatch:digital:immediate:{product_id}", None)

    if fulfilment_type == "physical":
        if inventory <= 0:
            cache.set(state_key, "backorder:physical")
            return DispatchResult(
                order_id, "backorder:physical", f"backorder:physical:notify:{customer_id}", None
            )
        if is_highval_phys:
            return _vip_path(order_id, customer_id, product_name, customer_tier, cache, orders_log, openai_client, state_key)
        cache.set(state_key, "processing:physical")
        return DispatchResult(order_id, "processing:physical", f"dispatch:physical:warehouse:{product_id}", None)

    sub_id = cust_data.get("subscription_id", "unknown")
    if is_highval_sub:
        return _vip_path(order_id, customer_id, product_name, customer_tier, cache, orders_log, openai_client, state_key)
    cache.set(state_key, "processing:subscription")
    return DispatchResult(order_id, "processing:subscription", f"dispatch:subscription:renew:{sub_id}", None)


def _vip_path(
    order_id: str,
    customer_id: str,
    product_name: str,
    customer_tier: str,
    cache: FileCache,
    orders_log: AppendLog,
    openai_client: OpenAI,
    state_key: str,
) -> DispatchResult:
    """High-value or VIP order — emit personalised confirmation email."""
    if customer_tier == "enterprise":
        prompt = (
            f"Generate a professional enterprise order confirmation for {customer_id} "
            f"ordering {product_name}. Mention dedicated account manager, priority SLA, "
            "and invoice terms."
        )
        max_tokens, disposition = 250, "processing:enterprise_vip"
        tag = "vip_enterprise"
    else:
        prompt = (
            f"Generate a warm VIP order confirmation for {customer_id} ordering "
            f"{product_name}. Mention priority handling, estimated delivery, and "
            "loyalty points."
        )
        max_tokens, disposition = 200, "processing:vip"
        tag = "vip"

    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.4,
    )
    email = completion.choices[0].message.content or ""
    cache.set(state_key, disposition)
    orders_log.append("orders", tag, order_id, email)
    return DispatchResult(order_id, disposition, "dispatch:vip", email)  # type: ignore[arg-type]


if __name__ == "__main__":
    import sys

    order_id = sys.argv[1] if len(sys.argv) > 1 else "ORD-0001"
    customer_id = sys.argv[2] if len(sys.argv) > 2 else "CUST-0001"
    product_id = sys.argv[3] if len(sys.argv) > 3 else "PROD-0001"
    order_value = float(sys.argv[4]) if len(sys.argv) > 4 else 600.0
    fulfilment: FulfilmentType = sys.argv[5] if len(sys.argv) > 5 else "physical"  # type: ignore[assignment]
    customer_api = "https://api.example.com/customers/"
    product_api = "https://api.example.com/products/"
    result = process_order(
        order_id, customer_id, product_id, order_value, fulfilment, customer_api, product_api,
    )
    print(json.dumps(vars(result), indent=2))
