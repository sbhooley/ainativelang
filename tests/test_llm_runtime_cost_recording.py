"""Test that LLMRuntimeAdapter automatically records costs when run_id is present."""
import uuid
from unittest.mock import patch, MagicMock
from adapters.llm_runtime import LLMRuntimeAdapter
from adapters.llm.base import LLMResponse, LLMUsage

def test_cost_recording_with_run_id():
    dummy_adapter = MagicMock()
    dummy_adapter.complete.return_value = LLMResponse(
        content="hello",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="test-model",
        provider="test",
    )
    adapter = LLMRuntimeAdapter(provider="test", config={"direct_adapter": dummy_adapter})

    # Mock CostTracker
    with patch("adapters.llm_runtime.CostTracker") as MockCT:
        ct_instance = MockCT.return_value
        result = adapter.call("completion", ["prompt", 100], context={"run_id": "test-run-123"})

        # Verify adapter called
        dummy_adapter.complete.assert_called_once()
        # Verify cost recording called with correct args
        ct_instance.add_cost.assert_called_once()
        args = ct_instance.add_cost.call_args[1]
        assert args["run_id"] == "test-run-123"
        assert args["provider"] == "test"
        assert args["model"] == "test-model"
        assert args["prompt_tokens"] == 10
        assert args["completion_tokens"] == 5
        # cost should be > 0 if estimate_cost returns something; otherwise just check it's passed
        assert "cost_usd" in args

def test_cost_recording_with_engine_style_run_id():
    """RuntimeEngine passes frame['_run_id'], not run_id."""
    dummy_adapter = MagicMock()
    dummy_adapter.complete.return_value = LLMResponse(
        content="hello",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="test-model",
        provider="test",
    )
    adapter = LLMRuntimeAdapter(provider="test", config={"direct_adapter": dummy_adapter})

    with patch("adapters.llm_runtime.CostTracker") as MockCT:
        ct_instance = MockCT.return_value
        adapter.call("completion", ["prompt", 100], context={"_run_id": "uuid-from-engine"})

        ct_instance.add_cost.assert_called_once()
        assert ct_instance.add_cost.call_args[1]["run_id"] == "uuid-from-engine"


def test_cost_recording_without_run_id():
    dummy_adapter = MagicMock()
    dummy_adapter.complete.return_value = LLMResponse(
        content="hello",
        usage=LLMUsage(1, 1, 2),
        model="m", provider="p",
    )
    adapter = LLMRuntimeAdapter(provider="t", config={"direct_adapter": dummy_adapter})

    with patch("adapters.llm_runtime.CostTracker") as MockCT:
        ct_instance = MockCT.return_value
        result = adapter.call("completion", ["p"], context={})  # no run_id
        ct_instance.add_cost.assert_not_called()
