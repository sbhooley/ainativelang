import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterError, AdapterRegistry

from adapters import langchain_tool as lt


def test_langchain_tool_adapter_call_dispatch_and_envelope():
    reg = AdapterRegistry(allowed=["langchain_tool"])
    reg.register("langchain_tool", lt.LangchainToolAdapter())

    out = reg.call("langchain_tool", "my_search_tool", ["hello"], {})
    assert out["ok"] is True
    assert out["tool"] == "my_search_tool"
    assert out["result"]["query"] == "hello"

    lt.register_langchain_tool("echo_tool", lambda x: {"echo": x})
    out2 = reg.call("langchain_tool", "CALL", ["echo_tool", "ping"], {})
    assert out2["ok"] and out2["result"] == {"echo": "ping"}


def test_langchain_tool_adapter_unknown_tool_raises():
    reg = AdapterRegistry(allowed=["langchain_tool"])
    reg.register("langchain_tool", lt.LangchainToolAdapter())
    try:
        reg.call("langchain_tool", "missing_xyz", [], {})
    except AdapterError as e:
        assert "no tool registered" in str(e).lower()
    else:
        raise AssertionError("expected AdapterError")
