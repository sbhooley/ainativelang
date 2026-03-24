# adapters/langchain_tool.py
"""
Invoke LangChain-compatible tools by name from AINL ``R`` steps.

Enable: ``--enable-adapter langchain_tool`` on the CLI host.

**Optional dependency:** ``langchain-core`` (and your tool definitions). If it is not
installed, only callables / objects registered via ``register_langchain_tool`` or
the built-in demo stub ``my_search_tool`` can run.

AINL (examples):

  # Shorthand: tool name is the verb after the adapter namespace (non-strict or strict when verb is allowlisted).
  R langchain_tool.my_search_tool "your query" -> result

  # Strict-friendly indirection: fixed CALL verb, first arg is tool name.
  R langchain_tool.CALL "my_search_tool" "your query" -> result

Register host tools from Python before running::

  from adapters.langchain_tool import register_langchain_tool
  register_langchain_tool("my_tool", your_structured_tool)

Env:
  (none required; extend via ``register_langchain_tool`` or subclassing.)
"""

from __future__ import annotations

from typing import Any, Dict, List, MutableMapping

from runtime.adapters.base import AdapterError, RuntimeAdapter

try:
    from langchain_core.tools import StructuredTool as _StructuredTool
except ImportError:  # pragma: no cover - optional dependency
    _StructuredTool = None  # type: ignore

LANGCHAIN_CORE_AVAILABLE = _StructuredTool is not None

# Process-wide registry: name -> BaseTool | StructuredTool | plain callable
_REGISTRY: MutableMapping[str, Any] = {}


def register_langchain_tool(name: str, tool: Any) -> None:
    """Register a LangChain tool or callable under ``name`` for ``langchain_tool`` dispatch."""
    key = str(name or "").strip()
    if not key:
        raise ValueError("register_langchain_tool: name must be non-empty")
    _REGISTRY[key] = tool


def _unwrap_lc_result(raw: Any) -> Any:
    """Normalize LangChain ToolMessage / Command wrappers to a JSON-friendly value."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    content = getattr(raw, "content", None)
    if content is not None:
        return content
    return raw


def _invoke_tool_object(tool: Any, invoke_args: List[Any]) -> Any:
    """Invoke a LangChain BaseTool, StructuredTool, or plain callable."""
    if tool is None:
        raise AdapterError("langchain_tool: tool object is None")

    if callable(tool) and not hasattr(tool, "invoke"):
        try:
            return tool(*invoke_args) if invoke_args else tool()
        except TypeError as e:
            raise AdapterError(f"langchain_tool: callable invocation failed: {e}") from e

    inv = getattr(tool, "invoke", None)
    if callable(inv):
        try:
            if len(invoke_args) == 0:
                raw = inv({})
            elif len(invoke_args) == 1:
                raw = inv(invoke_args[0])
            else:
                raw = inv({"args": invoke_args})
            return _unwrap_lc_result(raw)
        except Exception as e:
            raise AdapterError(f"langchain_tool: tool.invoke failed: {e}") from e

    run = getattr(tool, "run", None)
    if callable(run):
        try:
            if len(invoke_args) == 0:
                raw = run("")
            elif len(invoke_args) == 1:
                raw = run(invoke_args[0])
            else:
                raw = run(" ".join(str(x) for x in invoke_args))
            return _unwrap_lc_result(raw)
        except Exception as e:
            raise AdapterError(f"langchain_tool: tool.run failed: {e}") from e

    raise AdapterError("langchain_tool: registered object is not callable and has no invoke/run")


def _default_my_search_tool(*args: Any) -> Dict[str, Any]:
    """Offline demo tool when LangChain is not configured."""
    q = str(args[0]) if args else ""
    return {
        "query": q,
        "hits": [],
        "note": "demo stub: register a real tool via register_langchain_tool or install langchain-core",
    }


class LangchainToolAdapter(RuntimeAdapter):
    """Dispatch ``R langchain_tool.<tool_name> ...`` or ``R langchain_tool.CALL ...``."""

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip()
        if not verb:
            raise AdapterError("langchain_tool: missing tool name / verb (target)")

        tool_name: str
        invoke_args: List[Any]

        if verb.upper() == "CALL":
            if not args:
                raise AdapterError("langchain_tool.CALL requires at least tool_name as first argument")
            tool_name = str(args[0])
            invoke_args = list(args[1:])
        else:
            tool_name = verb
            invoke_args = list(args)

        tool = _REGISTRY.get(tool_name)
        if tool is None and tool_name == "my_search_tool":
            tool = _default_my_search_tool

        if tool is None:
            raise AdapterError(
                f"langchain_tool: no tool registered under name {tool_name!r}; "
                f"use adapters.langchain_tool.register_langchain_tool({tool_name!r}, tool)"
            )

        try:
            result = _invoke_tool_object(tool, invoke_args)
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"langchain_tool: execution error for {tool_name!r}: {e}") from e

        return {"ok": True, "tool": tool_name, "result": result}
