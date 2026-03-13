from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter
from runtime.values import coerce_number


class CoreBuiltinAdapter(RuntimeAdapter):
    """
    Builtin stdlib adapter namespace: core.*
    Supported targets include:
      add/sub/mul/div/min/max/clamp
      concat/split/join/lower/upper/replace
      parse/stringify
      now/iso/iso_ts/sleep
    """

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t = (target or "").strip().lower()
        def _num(v: Any) -> Any:
            if isinstance(v, (int, float)):
                return v
            if isinstance(v, str):
                s = v.strip()
                if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                    return int(s)
            return coerce_number(v)

        if t == "add":
            return _num(args[0]) + _num(args[1])
        if t == "sub":
            return _num(args[0]) - _num(args[1])
        if t == "mul":
            return _num(args[0]) * _num(args[1])
        if t == "div":
            b = _num(args[1])
            if b == 0:
                raise RuntimeError("division by zero")
            return _num(args[0]) / b
        if t == "min":
            return min(args)
        if t == "max":
            return max(args)
        if t == "clamp":
            x = coerce_number(args[0])
            lo = coerce_number(args[1])
            hi = coerce_number(args[2])
            return max(lo, min(hi, x))
        if t == "concat":
            return "".join(str(a) for a in args)
        if t == "split":
            return str(args[0]).split(str(args[1]))
        if t == "join":
            delim = str(args[0])
            arr = args[1] if len(args) > 1 else []
            return delim.join(str(x) for x in (arr or []))
        if t == "lower":
            return str(args[0]).lower()
        if t == "upper":
            return str(args[0]).upper()
        if t == "replace":
            return str(args[0]).replace(str(args[1]), str(args[2]))
        if t == "parse":
            return json.loads(str(args[0]))
        if t == "stringify":
            return json.dumps(args[0], ensure_ascii=False)
        if t == "now":
            return int(time.time())
        if t == "iso":
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if t == "iso_ts":
            ts = int(_num(args[0])) if args else int(time.time())
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        if t == "echo":
            return args[0] if args else None
        if t == "sleep":
            ms = int(float(args[0]))
            if ms > 0:
                time.sleep(ms / 1000.0)
            return None
        raise RuntimeError(f"unsupported core builtin target: {t}")
