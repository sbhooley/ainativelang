"""
Pytest configuration and shared fixtures for adapter tests.
"""

import pytest
import responses


@pytest.fixture
def mock_http():
    """Fixture that provides `responses` mock for HTTP calls."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def openrouter_success_response():
    """Return a successful OpenRouter-style response."""
    return {
        "id": "cmpl-123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "openrouter/gpt-4o-mini",
        "choices": [{"message": {"role": "assistant", "content": '{"result": "ok"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.fixture
def anthropic_success_response():
    return {
        "content": [{"type": "text", "text": '{"result": "ok"}'}],
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


@pytest.fixture
def cohere_success_response():
    return {
        "generations": [{"text": '{"result": "ok"}'}],
        "meta": {"billed_units": {"input_tokens": 10, "output_tokens": 5}},
    }
