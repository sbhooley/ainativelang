"""
Anthropic LLM Adapter (direct HTTP)

Implements the AbstractLLMAdapter using Anthropic's Messages API.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from adapters.llm.base import AbstractLLMAdapter, LLMResponse, LLMUsage
from .retry import retry_with_backoff

# Static pricing as of 2025-06 (USD per 1M tokens). Update manually if needed.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "claude-3-5-sonnet-20241022": {"prompt_price": 3.0, "completion_price": 15.0},
    "claude-3-5-haiku-20241022": {"prompt_price": 0.8, "completion_price": 4.0},
    "claude-3-opus-20240229": {"prompt_price": 15.0, "completion_price": 75.0},
    "claude-3-sonnet-20240229": {"prompt_price": 3.0, "completion_price": 15.0},
    "claude-3-haiku-20240307": {"prompt_price": 0.25, "completion_price": 1.25},
}


class AnthropicAdapter(AbstractLLMAdapter):
    """Adapter for Anthropic Claude via direct HTTP."""

    network_facing = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.api_key = self.config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("Anthropic API key missing (config['api_key'] or ANTHROPIC_API_KEY)")
        self.base_url = self.config.get("base_url", "https://api.anthropic.com/v1")
        self.json_mode = bool(self.config.get("json_mode", False))
        self.timeout = float(self.config.get("timeout_s", 60.0))

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def complete(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> LLMResponse:
        model = self.config.get("model", "claude-3-5-sonnet-20241022")
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}

        resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        resp.raise_for_status()

        data = resp.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        prompt_toks = usage.get("input_tokens", 0)
        completion_toks = usage.get("output_tokens", 0)

        return LLMResponse(
            content=content,
            usage=LLMUsage(
                prompt_tokens=prompt_toks,
                completion_tokens=completion_toks,
                total_tokens=prompt_toks + completion_toks,
            ),
            model=model,
            provider="anthropic",
            raw=data,
        )
    def validate(self) -> bool:
        # Quick health check: we have an API key and a known model
        model = self.config.get("model", "claude-3-5-sonnet-20241022")
        return bool(self.api_key) and model in MODEL_PRICING

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        model = self.config.get("model", "claude-3-5-sonnet-20241022")
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        prompt_price = pricing["prompt_price"] / 1_000_000
        completion_price = pricing["completion_price"] / 1_000_000
        return prompt_price * prompt_tokens + completion_price * completion_tokens

from ..registry import AdapterRegistry
AdapterRegistry.register_llm("anthropic", AnthropicAdapter)
