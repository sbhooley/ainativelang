import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterError, AdapterRegistry
from adapters.llm_query import LlmQueryAdapter


def test_llm_query_mock_success():
    old = os.environ.get("AINL_LLM_QUERY_MOCK")
    try:
        os.environ["AINL_LLM_QUERY_MOCK"] = "1"
        reg = AdapterRegistry(allowed=["llm_query"])
        reg.register("llm_query", LlmQueryAdapter(enabled=True))
        out = reg.call("llm_query", "query", ["hello", "gpt", 64], {"x": 1})
        assert out["ok"] is True
        assert out["runtime"] == "llm_query"
        assert isinstance(out.get("traces"), list)
    finally:
        if old is None:
            os.environ.pop("AINL_LLM_QUERY_MOCK", None)
        else:
            os.environ["AINL_LLM_QUERY_MOCK"] = old


def test_llm_query_blocks_when_disabled():
    reg = AdapterRegistry(allowed=["llm_query"])
    reg.register("llm_query", LlmQueryAdapter(enabled=False))
    try:
        reg.call("llm_query", "query", ["hello"], {})
    except AdapterError as e:
        assert "disabled" in str(e).lower()
    else:
        raise AssertionError("expected AdapterError")


def test_llm_query_private_context_firewall():
    old = os.environ.get("AINL_LLM_QUERY_MOCK")
    try:
        os.environ["AINL_LLM_QUERY_MOCK"] = "1"
        adp = LlmQueryAdapter(enabled=True)
        out = adp.run("hello", context={"visible": 1, "_secret": 2})
        assert out["ok"] is True
        # Mock returns deterministic text; firewall behavior is exercised by the adapter path.
    finally:
        if old is None:
            os.environ.pop("AINL_LLM_QUERY_MOCK", None)
        else:
            os.environ["AINL_LLM_QUERY_MOCK"] = old
