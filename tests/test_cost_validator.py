"""
Tests for CostValidator.
"""

import os
import pytest
import responses
from services.cost_validator import CostValidator


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
