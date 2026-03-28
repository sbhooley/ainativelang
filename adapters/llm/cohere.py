"""
Cohere LLM Adapter (direct HTTP)

Implements AbstractLLMAdapter using Cohere's Generate API.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from adapters.llm.base import AbstractLLMAdapter, LLMResponse, LLMUsage
from .retry import retry_with_backoff

# Static pricing as of 2025-06 (USD per 1M tokens). Update manually.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "command-r-plus": {"prompt_price": 3.0, "completion_price": 15.0},
    "command-r": {"prompt_price": 0.5, "completion_price": 1.5},
    "command-light": {"prompt_price": 0.2, "completion_price": 0.6},
}


class CohereAdapter(AbstractLLMAdapter):
    """Adapter for Cohere via direct HTTP."""

    network_facing = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.api_key = self.config.get("api_key") or os.environ.get("COHERE_API_KEY", "")
        if not self.api_key:
            raise ValueError("Cohere API key missing (config['api_key'] or COHERE_API_KEY)")
        self.base_url = self.config.get("base_url", "https://api.cohere.ai/v1")
        self.json_mode = bool(self.config.get("json_mode", False))
        self.timeout = float(self.config.get("timeout_s", 60.0))

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def complete(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> LLMResponse:
        model = self.config.get("model", "command-r-plus")
        url = f"{self.base_url.rstrip('/')}/generate"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens or 1024,
        }
        if self.json_mode:
            body["format"] = "json"

        resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        resp.raise_for_status()

        data = resp.json()
        text = data["generations"][0]["text"]
        usage = data.get("meta", {}).get("billed_units", {})
        prompt_toks = usage.get("input_tokens", 0)
        completion_toks = usage.get("output_tokens", 0)

        return LLMResponse(
            content=text,
            usage=LLMUsage(
                prompt_tokens=prompt_toks,
                completion_tokens=completion_toks,
                total_tokens=prompt_toks + completion_toks,
            ),
            model=model,
            provider="cohere",
            raw=data,
        )
    def validate(self) -> bool:
        model = self.config.get("model", "command-r-plus")
        return bool(self.api_key) and model in MODEL_PRICING

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        model = self.config.get("model", "command-r-plus")
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        prompt_price = pricing["prompt_price"] / 1_000_000
        completion_price = pricing["completion_price"] / 1_000_000
        return prompt_price * prompt_tokens + completion_price * completion_tokens

from ..registry import AdapterRegistry
AdapterRegistry.register_llm("cohere", CohereAdapter)
