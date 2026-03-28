"""
Tests for CohereAdapter using httpx mock.
"""

import pytest
import httpx
from adapters.llm.cohere import CohereAdapter


@pytest.fixture
def cohere_success_response():
    return {
        "generations": [{"text": '{"result": "ok"}'}],
        "meta": {"billed_units": {"input_tokens": 10, "output_tokens": 5}},
    }


def test_cohere_basic(monkeypatch, cohere_success_response):
    def mock_post(url, json=None, headers=None, timeout=None):
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=cohere_success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = CohereAdapter({"api_key": "test-key", "model": "command-r-plus"})
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result": "ok"}'
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 5
    assert resp.model == "command-r-plus"
    assert resp.provider == "cohere"


def test_cohere_json_mode(monkeypatch, cohere_success_response):
    def mock_post(url, json=None, headers=None, timeout=None):
        assert json.get("format") == "json"
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=cohere_success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = CohereAdapter({"api_key": "test-key", "model": "command-r", "json_mode": True})
    adapter.complete("test", max_tokens=50)


def test_cohere_validate():
    adapter = CohereAdapter({"api_key": "dummy"})
    assert adapter.validate() is True
    with pytest.raises(ValueError, match="Cohere API key missing"):
        CohereAdapter({})



def test_cohere_estimate_cost():
    adapter = CohereAdapter({"api_key": "dummy", "model": "command-r-plus"})
    cost = adapter.estimate_cost(1000, 500)
    expected = (3.0 * 1000 / 1_000_000) + (15.0 * 500 / 1_000_000)
    assert abs(cost - expected) < 1e-9

def test_cohere_429_retry(monkeypatch):
    """Test that 429 triggers retry and eventually succeeds."""
    call_count = {"n": 0}
    success_response = {
        "generations": [{"text": '{"result":"ok"}'}],
        "meta": {"billed_units": {"input_tokens": 10, "output_tokens": 5}},
    }

    def mock_post(url, json=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            req = httpx.Request('POST', url)
            return httpx.Response(429, text="rate limit", request=req)
        req = httpx.Request('POST', url)
        return httpx.Response(200, json=success_response, request=req)

    monkeypatch.setattr(httpx, "post", mock_post)
    adapter = CohereAdapter({"api_key": "***", "model": "command-r-plus"})
    resp = adapter.complete("Hello", max_tokens=100)
    assert resp.content == '{"result":"ok"}'
    assert call_count["n"] == 2
