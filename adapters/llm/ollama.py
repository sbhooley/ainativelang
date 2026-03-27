import requests
from .base import AbstractLLMAdapter, LLMResponse, LLMUsage

class OllamaAdapter(AbstractLLMAdapter):
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://ollama:11434")
        self.model = config.get("model", "llama2")
        if self.model.startswith("ollama/"):
            self.model = self.model.split("/", 1)[1]
        self.max_tokens = config.get("max_tokens", 800)
        self.session = requests.Session()
    
    def complete(self, prompt: str, max_tokens: int = None, **kwargs) -> LLMResponse:
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": kwargs.get("temperature", 0.7),
            }
        }
        resp = self.session.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        content = data["response"]
        prompt_tokens = len(prompt.split())
        completion_tokens = len(content.split())
        total_tokens = prompt_tokens + completion_tokens
        
        return LLMResponse(
            content=content,
            usage=LLMUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens),
            model=self.model,
            provider="ollama",
            raw=data
        )
    
    def validate(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            return self.model in models
        except Exception:
            return False
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

from ..registry import LLMAdapterRegistry
LLMAdapterRegistry.register_llm("ollama", OllamaAdapter)
