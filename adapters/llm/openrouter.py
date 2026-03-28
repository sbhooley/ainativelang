import os
import httpx
from .base import AbstractLLMAdapter, LLMResponse, LLMUsage
from .retry import retry_with_backoff

class InsufficientCreditsError(Exception):
    pass

class OpenRouterAdapter(AbstractLLMAdapter):
    network_facing = True

    COST_PER_1K_TOKENS = {
        "openai/gpt-4o-mini": (0.03, 0.06),
        "anthropic/claude-3-haiku": (0.025, 0.125),
        "stepfun/step-3.5-flash:free": (0.0, 0.0),  # free model
    }
    
    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required (config.api_key or OPENROUTER_API_KEY)")
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")
        self.referer = config.get("referer", "")
        self.title = config.get("title", "")
        self.model = config.get("model", "openai/gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 800)
        self.json_mode = config.get("json_mode", False)
        self.timeout = config.get("timeout", 60)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.referer:
            self.headers["HTTP-Referer"] = self.referer
        if self.title:
            self.headers["X-Title"] = self.title

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def complete(self, prompt: str, max_tokens: int = None, **kwargs) -> LLMResponse:
        if max_tokens is None:
            max_tokens = self.max_tokens
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if self.json_mode or "response_format" in kwargs:
            payload.setdefault("response_format", {"type": "json_object"})
        resp = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        if resp.status_code == 402:
            raise InsufficientCreditsError("OpenRouter balance insufficient")
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data["usage"]
        return LLMResponse(
            content=content,
            usage=LLMUsage(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            ),
            model=data["model"],
            provider="openrouter",
            raw=data,
        )

    def validate(self) -> bool:
        try:
            self.complete("ping", max_tokens=1)
            return True
        except Exception:
            return False

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        if self.model not in self.COST_PER_1K_TOKENS:
            return 0.0
        inp_rate, out_rate = self.COST_PER_1K_TOKENS[self.model]
        return (prompt_tokens / 1000) * inp_rate + (completion_tokens / 1000) * out_rate

from ..registry import LLMAdapterRegistry
LLMAdapterRegistry.register_llm("openrouter", OpenRouterAdapter)
