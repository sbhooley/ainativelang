import os
import requests
from .base import AbstractLLMAdapter, LLMResponse, LLMUsage

class InsufficientCreditsError(Exception):
    pass

class OpenRouterAdapter(AbstractLLMAdapter):
    COST_PER_1K_TOKENS = {
        "openai/gpt-4o-mini": (0.03, 0.06),
        "anthropic/claude-3-haiku": (0.025, 0.125),
    }
    
    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")
        self.referer = config.get("referer", "")
        self.title = config.get("title", "")
        self.model = config.get("model", "openai/gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 800)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.referer,
            "X-Title": self.title,
            "Content-Type": "application/json"
        })
    
    def complete(self, prompt: str, max_tokens: int = None, **kwargs) -> LLMResponse:
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]
        
        resp = self.session.post(f"{self.base_url}/chat/completions", json=payload, timeout=60)
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
                total_tokens=usage["total_tokens"]
            ),
            model=data["model"],
            provider="openrouter",
            raw=data
        )
    
    def validate(self) -> bool:
        try:
            self.complete("ping", max_tokens=5)
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
