"""Firm-profile helpers that sit beside the 1.8.2 decision ops.

These are opt-in except for the secret-name and cloud-key checks. A graph
that does not declare ``Uses`` keeps today's adapter set. A host that does
not set ``limits["now"]`` still reads the machine clock.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Optional

_CLOUD_KEY = re.compile(
    r"(?:"
    r"AKIA[0-9A-Z]{16}"
    r"|ASIA[0-9A-Z]{16}"
    r"|AccountKey=[A-Za-z0-9+/=]{20,}"
    r"|DefaultEndpointsProtocol="
    r"|SharedAccessSignature"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|sk-ant-[A-Za-z0-9_\-]{20,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
    r"|AIza[0-9A-Za-z_\-]{30,}"
    r"|ya29\.[0-9A-Za-z_\-]{20,}"
    r")"
)

_UNTRUSTED_START = "<<<UNTRUSTED_DOCUMENT>>>"
_UNTRUSTED_END = "<<<END_UNTRUSTED_DOCUMENT>>>"
_UNTRUSTED_CAP = 100_000

_SHAPE_TYPES = {"string", "number", "bool", "object", "array", "any"}


def source_contains_cloud_key(source: str) -> bool:
    """True when a compiled source contains a literal that looks like a key.

    The match is not returned. Callers report a fixed message so the key
    never lands in a diagnostic.
    """
    return bool(_CLOUD_KEY.search(source or ""))


def spends_completion(adapter: str, verb: str) -> bool:
    """True when this call can bill a model provider.

    The adapter name is not the budget. ``openrouter.completion`` spends
    the same way ``llm.COMPLETION`` does. ``llm_query`` and
    ``embedding_memory`` are included because those clients call a model
    under a different verb.
    """
    name = (adapter or "").strip().lower()
    action = (verb or "").strip().lower()
    if action in {"completion", "embed"}:
        return True
    if name == "llm_query" and action in {"query", "run"}:
        return True
    if name == "embedding_memory" and action in {"upsert_ref", "index", "search", "query"}:
        return True
    return False


def clock_unix(limits: Optional[Dict[str, Any]], fallback: int) -> int:
    """Return the host clock. ``limits["now"]`` is a unix second when set."""
    raw = (limits or {}).get("now") if isinstance(limits, dict) else None
    if raw is None:
        return int(fallback)
    return int(raw)


def _break_marker(text: str, marker: str) -> str:
    broken = marker[:-1] + "\u200b>"
    return text.replace(marker, broken)


def untrusted_prompt(instructions: Any, document: Any) -> Any:
    """Wrap a document so it cannot close the instruction block.

    The document is one field. The instructions are another. A copy of the
    closing marker inside the document is broken with a zero-width space.
    Over the character cap this returns an error value and does not include
    the document.
    """
    text = "" if document is None else str(document)
    if len(text) > _UNTRUSTED_CAP:
        return {
            "error": {
                "code": "UNTRUSTED_LIMIT",
                "message": "untrusted document exceeds 100000 characters",
            }
        }
    safe = _break_marker(_break_marker(text, _UNTRUSTED_END), _UNTRUSTED_START)
    lead = "" if instructions is None else str(instructions)
    return f"{lead}\n\n{_UNTRUSTED_START}\n{safe}\n{_UNTRUSTED_END}"


def _shape_ok(value: Any, kind: str) -> bool:
    if kind == "any":
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    return False


def apply_shape(value: Any, fields: Iterable[Any]) -> Any:
    """Keep only the declared fields. A missing field is an error value.

    The message names the field. It does not include the model object.
    """
    specs: List[tuple] = []
    for raw in fields:
        text = str(raw or "").strip()
        if not text:
            continue
        name, sep, kind = text.partition(":")
        kind = (kind or "any").strip().lower()
        name = name.strip()
        if not sep or not name or kind not in _SHAPE_TYPES:
            return {
                "error": {
                    "code": "SHAPE_TYPE",
                    "message": "shape field must be name:type",
                }
            }
        specs.append((name, kind))
    if not isinstance(value, dict):
        return {
            "error": {
                "code": "SHAPE_TYPE",
                "message": "shape value must be an object",
            }
        }
    out: Dict[str, Any] = {}
    for name, kind in specs:
        if name not in value:
            return {
                "error": {
                    "code": "SHAPE_MISSING",
                    "message": f"shape field {name} is missing",
                }
            }
        got = value[name]
        if not _shape_ok(got, kind):
            return {
                "error": {
                    "code": "SHAPE_TYPE",
                    "message": f"shape field {name} has the wrong type",
                }
            }
        out[name] = copy.deepcopy(got)
    return out


def stamp_idempotency(message: Any, key: str) -> Any:
    """Copy a dict message and set ``idempotency_key`` when it is absent.

    A non-dict message is returned as-is. The key is still the third
    argument the host adapter receives.
    """
    if not isinstance(message, dict):
        return message
    out = copy.deepcopy(message)
    out.setdefault("idempotency_key", key)
    return out
