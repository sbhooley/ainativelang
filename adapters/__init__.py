"""
Adapters: pluggable backends for R (db, api), P (pay), Sc (scrape).
Replace mock adapters with real implementations (Prisma, Stripe, etc.).
"""
from .base import (
    AdapterRegistry,
    APIAdapter,
    AuthAdapter,
    CacheAdapter,
    DBAdapter,
    PayAdapter,
    QueueAdapter,
    ScrapeAdapter,
    TxnAdapter,
)
from .mock import mock_registry

# LLM adapter family (new)
from .registry import LLMAdapterRegistry  # noqa: F401
from .llm.base import AbstractLLMAdapter, LLMResponse, LLMUsage  # noqa: F401
from .llm.openrouter import OpenRouterAdapter  # noqa: F401
from .llm.ollama import OllamaAdapter  # noqa: F401
from .llm.offline import OfflineLLMAdapter  # noqa: F401
from .llm.anthropic import AnthropicAdapter  # noqa: F401
from .llm.cohere import CohereAdapter  # noqa: F401
from .llm_runtime import LLMRuntimeAdapter  # noqa: F401
from .fallback import FallbackLLMAdapter, CircuitBreaker, create_fallback_from_config  # noqa: F401

__all__ = [
    # Core adapters
    "AdapterRegistry",
    "DBAdapter",
    "APIAdapter",
    "AuthAdapter",
    "CacheAdapter",
    "PayAdapter",
    "QueueAdapter",
    "ScrapeAdapter",
    "TxnAdapter",
    "mock_registry",
    # LLM adapters
    "LLMAdapterRegistry",
    "AbstractLLMAdapter",
    "LLMResponse",
    "LLMUsage",
    "OpenRouterAdapter",
    "OllamaAdapter",
    "OfflineLLMAdapter",
    "AnthropicAdapter",
    "CohereAdapter",
    "LLMRuntimeAdapter",
    "FallbackLLMAdapter",
    "CircuitBreaker",
    "create_fallback_from_config",
]

def register_llm_adapters(runtime_registry: AdapterRegistry, config: dict) -> None:
    """
    Bootstrap LLM adapters into the runtime.

    Constructs a fallback chain according to config and registers a
    runtime adapter named "llm". Also registers each individual provider
    if you want fine-grained control.

    Args:
        runtime_registry: RuntimeAdapterRegistry instance (from runtime.adapters.base)
        config: Configuration dict (typically loaded from YAML)
    """
    from .registry import LLMAdapterRegistry
    from .fallback import create_fallback_from_config

    # Build fallback adapter from config
    try:
        fallback = create_fallback_from_config(config, LLMAdapterRegistry)
    except Exception as e:
        raise RuntimeError(f"Failed to build LLM fallback chain: {e}") from e

    # Register a composite "llm" runtime adapter that uses the fallback
    runtime_registry.register("llm", LLMRuntimeAdapter(provider="llm", config={"direct_adapter": fallback}))

    # Also register each provider individually (optional, but convenient)
    llm_cfg = config.get("llm", {})
    chain = llm_cfg.get("fallback_chain", [])
    for provider in chain:
        # Each provider's runtime adapter will use its own adapter (no fallback)
        # Note: individual adapters still have their own CircuitBreaker if wrapped
        # We'll create a separate runtime adapter per provider that bypasses fallback.
        # For simplicity, we can register them by creating a direct LLMRuntimeAdapter for the provider.
        # The fallback is only used for the "llm" alias.
        try:
            prov_adapter = LLMAdapterRegistry.get_llm_adapter(provider, llm_cfg.get("providers", {}).get(provider, {}))
            # Wrap in a simple runtime adapter (no fallback, but still subject to individual circuit breaker if we integrate it differently)
            # For now, we just register a direct runtime adapter; the CircuitBreaker is inside the fallback's chain, not per-adapter.
            # To have per-adapter circuit breaker visible even when called directly, we could also wrap each with a breaker. But phase 1 focuses on fallback.
            runtime_registry.register(provider, LLMRuntimeAdapter(provider=provider, config={"direct_adapter": prov_adapter}))
        except Exception:
            # Skip if provider fails to load
            pass
