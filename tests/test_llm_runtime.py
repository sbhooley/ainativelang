"""
Tests for LLMRuntimeAdapter.
"""

import pytest
from adapters.llm_runtime import LLMRuntimeAdapter
from adapters.llm.base import LLMResponse, LLMUsage
from runtime.adapters.base import AdapterError


class DummyLLMAdapter:
    def __init__(self):
        self.called = False
    def complete(self, prompt, max_tokens=None):
        self.called = True
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return LLMResponse(content="hello", usage=LLMUsage(1,2,3), model="dummy", provider="dummy")
    def validate(self):
        return True
    def estimate_cost(self, pt, ct):
        return 0.0


def test_llm_runtime_with_direct_adapter():
    dummy = DummyLLMAdapter()
    adapter = LLMRuntimeAdapter(provider="dummy", config={"direct_adapter": dummy})
    result = adapter.call("completion", ["test prompt", 100])
    assert result["content"] == "hello"
    assert dummy.called is True
    assert dummy.last_prompt == "test prompt"
    assert dummy.last_max_tokens == 100


def test_llm_runtime_unsupported_target():
    dummy = DummyLLMAdapter()
    adapter = LLMRuntimeAdapter(provider="dummy", config={"direct_adapter": dummy})
    with pytest.raises(AdapterError):
        adapter.call("unknown", ["prompt"])


def test_llm_runtime_missing_prompt():
    dummy = DummyLLMAdapter()
    adapter = LLMRuntimeAdapter(provider="dummy", config={"direct_adapter": dummy})
    with pytest.raises(AdapterError):
        adapter.call("completion", [])
