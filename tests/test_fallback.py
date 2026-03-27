"""
Tests for FallbackLLMAdapter.
"""

import pytest
from adapters.fallback import FallbackLLMAdapter, CircuitBreaker
from adapters.llm.base import AbstractLLMAdapter, LLMResponse, LLMUsage


class SuccessAdapter(AbstractLLMAdapter):
    def __init__(self, name="success"):
        self.name = name
    def complete(self, prompt, max_tokens=None, **kwargs):
        return LLMResponse(content="ok", usage=LLMUsage(1,1,2), model="test", provider=self.name)
    def validate(self):
        return True
    def estimate_cost(self, pt, ct):
        return 0.0


class FailAdapter(AbstractLLMAdapter):
    def __init__(self, name="fail"):
        self.name = name
    def complete(self, prompt, max_tokens=None, **kwargs):
        raise RuntimeError(f"{self.name} failed")
    def validate(self):
        return True
    def estimate_cost(self, pt, ct):
        return 0.0


def test_fallback_primary_succeeds():
    adapters = [
        (SuccessAdapter("first"), CircuitBreaker("first")),
        (FailAdapter("second"), CircuitBreaker("second")),
    ]
    fb = FallbackLLMAdapter(adapters)
    resp = fb.complete("test")
    assert resp.content == "ok"
    assert resp.provider == "first"


def test_fallback_primary_fails_uses_backup():
    adapters = [
        (FailAdapter("first"), CircuitBreaker("first")),
        (SuccessAdapter("second"), CircuitBreaker("second")),
    ]
    fb = FallbackLLMAdapter(adapters)
    resp = fb.complete("test")
    assert resp.content == "ok"
    assert resp.provider == "second"


def test_fallback_all_fail():
    adapters = [
        (FailAdapter("a"), CircuitBreaker("a")),
        (FailAdapter("b"), CircuitBreaker("b")),
    ]
    fb = FallbackLLMAdapter(adapters)
    with pytest.raises(RuntimeError):
        fb.complete("test")


def test_fallback_validate():
    adapters = [
        (SuccessAdapter("a"), CircuitBreaker("a")),
        (SuccessAdapter("b"), CircuitBreaker("b")),
    ]
    fb = FallbackLLMAdapter(adapters)
    assert fb.validate() is True
    # If all adapters invalid, should return False
    adapters_invalid = [
        (FailAdapter("x"), CircuitBreaker("x")),  # validate returns True still; we need an invalid one. Let's create InvalidAdapter
    ]
    # We can override validate to return False
    class InvalidAdapter(AbstractLLMAdapter):
        def complete(self, *a, **kw): pass
        def validate(self): return False
        def estimate_cost(self, pt, ct): return 0.0
    adapters_invalid = [(InvalidAdapter(), CircuitBreaker("inv"))]
    fb_inv = FallbackLLMAdapter(adapters_invalid)
    assert fb_inv.validate() is False
