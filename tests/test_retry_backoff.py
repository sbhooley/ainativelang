"""Test retry_with_backoff decorator for LLM adapters."""
import httpx
import pytest
from adapters.llm.retry import retry_with_backoff
from adapters.llm.anthropic import AnthropicAdapter
from adapters.llm.cohere import CohereAdapter

def make_429_on_first_call(success_response):
    call_count = {"n": 0}
    def mock_post(url, json=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            req = httpx.Request('POST', url)
            return httpx.Response(429, text="rate limit", request=req)
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=success_response, request=req)
    return mock_post, call_count

def test_anthropic_retry_429(monkeypatch):
    success_response = {
        "content": [{"type": "text", "text": '{"result":"ok"}'}],
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    mock_post, call_count = make_429_on_first_call(success_response)
    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = AnthropicAdapter({"api_key": "***", "model": "claude-3-5-sonnet-20241022"})
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result":"ok"}'
    # With retry, we expect 2 calls: first 429, second 200
    assert call_count["n"] == 2

def test_cohere_retry_429(monkeypatch):
    success_response = {
        "generations": [{"text": '{"result":"ok"}'}],
        "meta": {"billed_units": {"input_tokens": 10, "output_tokens": 5}},
    }
    mock_post, call_count = make_429_on_first_call(success_response)
    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = CohereAdapter({"api_key": "***", "model": "command-r-plus"})
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result":"ok"}'
    assert call_count["n"] == 2

def test_retry_non_429_raises_immediately(monkeypatch):
    """Test that non-retryable errors (e.g., 400) are raised without retry."""
    def mock_post(url, json=None, headers=None, timeout=None):
        req = httpx.Request('POST', url)
        return httpx.Response(400, text="bad request", request=req)
    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = AnthropicAdapter({"api_key": "***", "model": "claude-3-5-sonnet-20241022"})
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        adapter.complete("Hello", max_tokens=100)
    assert excinfo.value.response.status_code == 400
