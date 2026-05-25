from __future__ import annotations

import json
from typing import Any, Dict, List


def truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v != ""
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return bool(v)


def coerce_number(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(v.strip())
    raise ValueError(f"cannot coerce to number: {v!r}")


def compare(a: Any, op: str, b: Any) -> bool:
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    raise ValueError(f"unsupported compare op: {op}")


def deep_get(obj: Any, path: str, default: Any = None) -> Any:
    cur = obj
    for part in (path or "").split("."):
        if part == "":
            continue
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        elif isinstance(cur, list):
            if not part.isdigit():
                return default
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return default
            cur = cur[idx]
        else:
            return default
    return cur


def deep_put(obj: Any, path: str, value: Any) -> Any:
    if not isinstance(obj, dict):
        obj = {}
    parts = [p for p in (path or "").split(".") if p]
    if not parts:
        return value
    cur = obj
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value
    return obj


def stable_sort(rows: List[Any], field: str, desc: bool = False) -> List[Any]:
    def comparable_value(v: Any) -> Any:
        if isinstance(v, bool):
            return ("bool", v)
        if isinstance(v, (int, float)):
            return ("number", v)
        if isinstance(v, str):
            return ("str", v)
        try:
            return (type(v).__name__, json.dumps(json_safe(v), sort_keys=True, ensure_ascii=False))
        except TypeError:
            return (type(v).__name__, str(v))

    def key_fn(x: Any) -> Any:
        if isinstance(x, dict):
            v = x.get(field)
            return (v is None, comparable_value(v) if v is not None else None)
        return (True, None)

    return sorted(rows or [], key=key_fn, reverse=desc)


def json_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): json_safe(val) for k, val in v.items()}
    if isinstance(v, list):
        return [json_safe(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def encode_json(v: Any) -> str:
    return json.dumps(json_safe(v), ensure_ascii=False)
