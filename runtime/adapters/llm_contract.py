"""Host-owned model calls.

The graph asks for a completion or an embedding. It does not name an endpoint
or read a key. The host callback owns managed identity, quota, and failover.
``core.ENV`` is not a secret loader.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter


def _usage(raw: Any) -> Dict[str, int]:
    src = raw if isinstance(raw, dict) else {}
    prompt = int(src.get("prompt_tokens") or 0)
    completion = int(src.get("completion_tokens") or 0)
    total = int(src.get("total_tokens") or (prompt + completion))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def _parse_content(content: str) -> Any:
    text = (content or "").strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def completion_value(
    *,
    status: str,
    content: Any = "",
    parsed: Any = None,
    usage: Any = None,
) -> Dict[str, Any]:
    """The object ``llm.COMPLETION`` returns to the graph."""
    state = str(status or "error")
    if state not in {"ok", "content_filter", "error"}:
        state = "error"
    text = "" if content is None else str(content)
    if parsed is None and state == "ok":
        parsed = _parse_content(text)
    return {
        "status": state,
        "content": text,
        "parsed": parsed,
        "usage": _usage(usage),
    }


def embed_value(vector: Any) -> List[float]:
    if not isinstance(vector, list) or not vector:
        raise AdapterError("llm embed returned no vector")
    out: List[float] = []
    for item in vector:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise AdapterError("llm embed vector must be numbers")
        out.append(float(item))
    return out


class CallbackLlmAdapter(RuntimeAdapter):
    """Completion and embed through host callbacks. No environment reads."""

    def __init__(
        self,
        complete: Callable[[str], Any],
        embed: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._complete = complete
        self._embed = embed

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().upper()
        if verb == "COMPLETION":
            prompt = "" if not args else str(args[0])
            raw = self._complete(prompt)
            if isinstance(raw, dict) and "status" in raw:
                return completion_value(
                    status=str(raw.get("status") or "ok"),
                    content=raw.get("content", ""),
                    parsed=raw.get("parsed"),
                    usage=raw.get("usage"),
                )
            return completion_value(status="ok", content="" if raw is None else str(raw))
        if verb == "EMBED":
            if self._embed is None:
                raise AdapterError("llm embed is not configured")
            text = "" if not args else str(args[0])
            return embed_value(self._embed(text))
        raise AdapterError(f"unsupported llm target: {verb}")
