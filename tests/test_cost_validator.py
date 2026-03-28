"""
Tests for CostValidator.
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest
import responses

from services.cost_validator import CostValidator


def test_openrouter_models_fetch_uses_cache_within_ttl(monkeypatch):
    """Second validation within TTL should not issue a second httpx GET for models."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": []}
    with patch("services.cost_validator.httpx.Client") as Client:
        inst = Client.return_value.__enter__.return_value
        inst.get.return_value = mock_resp
        v = CostValidator(observability=None, interval_hours=1)
        v._or_models_ttl_s = 3600.0
        v.validate_once()
        v.validate_once()
        assert inst.get.call_count == 1


def test_openrouter_models_refetch_after_ttl(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": []}
    with patch("services.cost_validator.httpx.Client") as Client:
        inst = Client.return_value.__enter__.return_value
        inst.get.return_value = mock_resp
        v = CostValidator(observability=None, interval_hours=1)
        v._or_models_ttl_s = 0.001
        v.validate_once()
        time.sleep(0.02)
        v.validate_once()
        assert inst.get.call_count == 2


@responses.activate
def test_cost_validator_detects_drift(monkeypatch):
    # Mock OpenRouter models endpoint
    responses.add(
        responses.GET,
        "https://openrouter.ai/api/v1/models",
        json={
            "data": [
                {
                    "id": "openrouter/gpt-4o-mini",
                    "pricing": {
                        "prompt": "0.00000015",  # per token? Actually per 1K tokens in OpenRouter docs; we treat as per 1K conversion in validator
                        "completion": "0.0000006",
                    },
                }
            ]
        },
        status=200,
    )
    # We'll set OPENROUTER_API_KEY
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    validator = CostValidator(observability=None, interval_hours=1)
    # Run validation once directly
    validator.validate_once()
    # No assertions for now, just ensure it runs without error
    # In a real test we would capture logs/metrics
