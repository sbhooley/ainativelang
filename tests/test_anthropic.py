"""
Tests for AnthropicAdapter using httpx mock.
"""

import pytest
import httpx
from adapters.llm.anthropic import AnthropicAdapter


@pytest.fixture
def anthropic_success_response():
    return {
        "content": [{"type": "text", "text": '{"result": "ok"}'}],
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def test_anthropic_basic(monkeypatch, anthropic_success_response):
    def mock_post(url, json=None, headers=None, timeout=None):
        # Build a Response with a dummy request to satisfy raise_for_status
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=anthropic_success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = AnthropicAdapter({"api_key": "test-key", "model": "claude-3-5-sonnet-20241022"})
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result": "ok"}'
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 5
    assert resp.model == "claude-3-5-sonnet-20241022"
    assert resp.provider == "anthropic"


def test_anthropic_json_mode(monkeypatch, anthropic_success_response):
    def mock_post(url, json=None, headers=None, timeout=None):
        # check json body includes response_format
        assert json.get("response_format") == {"type": "json_object"}
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=anthropic_success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = AnthropicAdapter({"api_key": "test-key", "model": "claude-3-5-haiku-20241022", "json_mode": True})
    adapter.complete("test", max_tokens=50)


def test_anthropic_429_retry(monkeypatch, anthropic_success_response):
    call_count = {"n": 0}

    def mock_post(url, json=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            req = httpx.Request('POST', url)
            return httpx.Response(429, text="rate limit", request=req)
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=anthropic_success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = AnthropicAdapter({"api_key": "***", "model": "claude-3-5-sonnet-20241022"})
    # With retry, this call should succeed after one retry (2 attempts total)
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result": "ok"}'
    # Total HTTP calls should be 2 (first 429, second 200)
    assert call_count["n"] == 2
def test_anthropic_validate():
    # With a valid API key (dummy), adapter is considered valid structurally
    adapter = AnthropicAdapter({"api_key": "dummy"})
    assert adapter.validate() is True
    # Without an API key, construction should fail
    with pytest.raises(ValueError, match="Anthropic API key missing"):
        AnthropicAdapter({})



def test_anthropic_estimate_cost():
    adapter = AnthropicAdapter({"api_key": "dummy", "model": "claude-3-5-sonnet-20241022"})
    cost = adapter.estimate_cost(1000, 500)
    expected = (3.0 * 1000 / 1_000_000) + (15.0 * 500 / 1_000_000)
    assert abs(cost - expected) < 1e-9
