from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage
    model: str
    provider: str
    raw: Optional[Any] = None

class AbstractLLMAdapter(ABC):
    """LLM providers; subclasses set network_facing for policy / capability discovery."""

    network_facing: bool = False

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int, **kwargs) -> LLMResponse:
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        pass
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0
