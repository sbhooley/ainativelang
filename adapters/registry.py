class LLMAdapterRegistry:
    _llm_adapters = {}
    
    @classmethod
    def register_llm(cls, provider: str, adapter_cls):
        cls._llm_adapters[provider] = adapter_cls
    
    @classmethod
    def get_llm_adapter(cls, provider: str, config: dict):
        if provider not in cls._llm_adapters:
            raise ValueError(f"Unknown LLM provider: {provider}")
        return cls._llm_adapters[provider](config)
    
    @classmethod
    def list_providers(cls):
        return list(cls._llm_adapters.keys())

# Ensure built-in LLM adapters are registered on import.
# These imports have side effects that register providers.
try:
    from adapters.llm import openrouter as _openrouter_adapter  # noqa: F401
    from adapters.llm import ollama as _ollama_adapter  # noqa: F401
except Exception:
    # Adapters are optional; registry can still be used without them.
    pass

# Backward compatibility: older modules import AdapterRegistry from this file.
AdapterRegistry = LLMAdapterRegistry
