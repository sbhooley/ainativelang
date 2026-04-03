"""Offline / deterministic LLM provider (no network). For tests and config.yaml demos."""

from __future__ import annotations

from .base import AbstractLLMAdapter, LLMResponse, LLMUsage
from ..registry import LLMAdapterRegistry


class OfflineLLMAdapter(AbstractLLMAdapter):
    """
    Returns deterministic text from the prompt (no HTTP). Register as provider ``offline``
    and put it in ``llm.fallback_chain`` for CI or local runs without API keys.
    """

    network_facing = False

    def __init__(self, config: dict):
        self._prefix = str((config or {}).get("prefix", "OFFLINE_LLM"))

    def complete(self, prompt: str, max_tokens: int = None, **kwargs) -> LLMResponse:
        p = str(prompt or "")
        body = f"{self._prefix}:{p[:2000]}"
        prompt_tokens = max(1, len(p.split()))
        completion_tokens = max(1, len(body.split()))
        return LLMResponse(
            content=body,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model="offline",
            provider="offline",
            raw={"offline": True},
        )

    def validate(self) -> bool:
        return True

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0


LLMAdapterRegistry.register_llm("offline", OfflineLLMAdapter)
