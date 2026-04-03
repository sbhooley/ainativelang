"""
Integration tests for LLM adapter bootstrap.
"""

from runtime.adapters.base import AdapterRegistry as RuntimeAdapterRegistry
from adapters import register_llm_adapters
from adapters.fallback import FallbackLLMAdapter


def test_register_llm_adapters_registers_llm_and_providers():
    config = {
        "llm": {
            "fallback_chain": ["openrouter", "ollama"],
            "circuit_breaker": {"failure_threshold": 3, "recovery_timeout_s": 60},
            "providers": {
                "openrouter": {"api_key": "dummy"},
                "ollama": {"base_url": "http://localhost:11434"}
            }
        }
    }
    runtime_reg = RuntimeAdapterRegistry(allowed=["core", "llm"])
    register_llm_adapters(runtime_reg, config)

    assert "llm" in runtime_reg._adapters
    assert "openrouter" in runtime_reg._adapters
    assert "ollama" in runtime_reg._adapters

    # The 'llm' adapter should have a fallback chain
    llm_adapter = runtime_reg._adapters["llm"]
    # LLMRuntimeAdapter with direct_adapter being a FallbackLLMAdapter
    assert hasattr(llm_adapter, "_direct_adapter")
    assert isinstance(llm_adapter._direct_adapter, FallbackLLMAdapter)
    # The fallback should have 2 adapters inside
    assert len(llm_adapter._direct_adapter._adapters_with_breakers) == 2


def test_register_llm_adapters_offline_provider_no_network():
    config = {
        "llm": {
            "fallback_chain": ["offline"],
            "providers": {"offline": {"prefix": "TEST_OFFLINE"}},
        }
    }
    runtime_reg = RuntimeAdapterRegistry(allowed=["core", "llm"])
    register_llm_adapters(runtime_reg, config)
    llm_adapter = runtime_reg._adapters["llm"]
    out = llm_adapter.call("completion", ["hello"], {})
    assert isinstance(out, dict)
    assert out.get("content", "").startswith("TEST_OFFLINE:")
