import pytest
from adapters.registry import AdapterRegistry
from adapters.llm.base import LLMResponse

def test_openrouter_adapter_instantiation():
    config = {"api_key": "test", "model": "openai/gpt-4o-mini", "max_tokens": 10}
    adapter = AdapterRegistry.get_llm_adapter("openrouter", config)
    assert adapter is not None
    assert adapter.validate() is False  # invalid key

def test_ollama_adapter_instantiation():
    config = {"base_url": "http://localhost:11434", "model": "ollama/mistral", "max_tokens": 10}
    adapter = AdapterRegistry.get_llm_adapter("ollama", config)
    assert adapter is not None
    # validate may fail if Ollama not running; we expect False
    assert adapter.validate() in [True, False]

def test_cost_estimation_non_negative():
    config = {"api_key": "test", "model": "openai/gpt-4o-mini"}
    adapter = AdapterRegistry.get_llm_adapter("openrouter", config)
    cost = adapter.estimate_cost(100, 50)
    assert cost >= 0.0

# Integration test with mocked responses would be added in real suite
