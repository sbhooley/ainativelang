"""
LLM Runtime Adapter Bridge

Bridges the AINL runtime's generic RuntimeAdapter interface to the
AbstractLLMAdapter registry. This allows LLM providers to be used as
standard runtime adapters in R steps.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.adapters.base import RuntimeAdapter, AdapterError

from adapters.registry import LLMAdapterRegistry
from adapters.llm.base import AbstractLLMAdapter, LLMResponse, LLMUsage


class LLMRuntimeAdapter(RuntimeAdapter):
    """
    Runtime adapter that proxies calls to an AbstractLLMAdapter.
    Can be constructed either with a provider name (looked up via LLMAdapterRegistry)
    or with a direct adapter instance via config["direct_adapter"].
    """

    def __init__(self, provider: str, config: Optional[Dict[str, Any]] = None):
        self.provider = provider
        self.config = config or {}
        self._adapter: Optional[AbstractLLMAdapter] = None
        self._direct_adapter: Optional[AbstractLLMAdapter] = self.config.get("direct_adapter")

    def _get_adapter(self) -> AbstractLLMAdapter:
        if self._adapter is None:
            if self._direct_adapter is not None:
                return self._direct_adapter
            try:
                self._adapter = LLMAdapterRegistry.get_llm_adapter(self.provider, self.config)
            except Exception as e:
                raise AdapterError(f"Failed to load LLM adapter '{self.provider}': {e}") from e
        return self._adapter

    def call(self, target: str, args: List[Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        RuntimeAdapter.call implementation.
        For LLM adapters, target is the method name (currently only 'completion' supported).
        args expected: [prompt: str, max_tokens: int (optional)]
        Returns dict with keys: 'content', 'usage' (with prompt_tokens, completion_tokens, total_tokens)
        """
        if target != "completion":
            raise AdapterError(f"Unsupported target for LLM adapter: {target}. Use 'completion'.")
        if not args:
            raise AdapterError("LLM completion requires at least a prompt argument")
        prompt = str(args[0])
        max_tokens = int(args[1]) if len(args) > 1 and args[1] is not None else None

        adapter = self._get_adapter()
        try:
            resp: LLMResponse = adapter.complete(prompt=prompt, max_tokens=max_tokens)
        except Exception as e:
            raise AdapterError(f"LLM call failed ({self.provider}): {e}") from e

        return {
            "content": resp.content,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            },
            "model": resp.model,
            "provider": resp.provider,
        }
