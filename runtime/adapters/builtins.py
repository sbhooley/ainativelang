from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter
from runtime.values import coerce_number, deep_get


class CoreBuiltinAdapter(RuntimeAdapter):
    """
    Builtin stdlib adapter namespace: core.*
    Supported targets include:
      add/sub/mul/div/idiv/min/max/clamp
      eq/neq/gt/lt/gte/lte — comparisons (return bool)
      concat/split/join/lower/upper/replace/contains
      startswith(s, prefix) / endswith(s, suffix) — string predicates
      trim(s) — collapse all internal whitespace to single space + strip edges
      strip(s) / lstrip(s) / rstrip(s) — edge whitespace removal
      substr(s, start, length) — string slice
      str(v)/int(v)/float(v) — type coercions (aliases: tostring/toint/tofloat/string)
      env(name, default?) — os.getenv
      parse/stringify
      keys(dict) / values(dict) — dict introspection
      merge(dict...) — shallow-merge dict args left-to-right; non-dicts skipped
      len(x) — length of str/list/dict (non-collections stringified)
      now/iso/iso_ts/sleep/echo
      filter_high_score(list, min) — keep dict items with score/relevance >= min
      id(value) — identity; returns first arg (used to materialize object literals in R lines)
      get(obj, key) — deep key/index read (objects and lists)
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
        if t == "idiv":
            b = _num(args[1])
            if b == 0:
                raise RuntimeError("division by zero")
            return int(_num(args[0]) // b)
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
        if t == "contains":
            # substring search: needle in haystack (string coercion; empty needle -> True)
            hay = str(args[0]) if args else ""
            needle = str(args[1]) if len(args) > 1 else ""
            if needle == "":
                return True
            return needle in hay
        if t == "get":
            return deep_get(args[0], str(args[1])) if len(args) >= 2 else None
        if t == "parse":
            return json.loads(str(args[0]))
        if t == "stringify":
            return json.dumps(args[0], ensure_ascii=False)
        if t == "merge":
            out: Dict[str, Any] = {}
            for arg in args:
                if isinstance(arg, dict):
                    out.update(arg)
            return out
        if t == "len":
            x = args[0] if args else None
            if x is None:
                return 0
            if isinstance(x, (list, dict, str, bytes, bytearray)):
                return len(x)
            try:
                return len(x)  # type: ignore[arg-type]
            except Exception:
                return len(str(x))
        if t == "now":
            return int(time.time())
        if t == "iso":
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if t == "iso_ts":
            ts = int(_num(args[0])) if args else int(time.time())
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        if t in ("echo", "id"):
            return args[0] if args else None
        if t == "env":
            # os.getenv(name, default=None); optional second arg is default string
            name = str(args[0]) if args else ""
            if not name:
                return None
            default = None if len(args) < 2 else args[1]
            return os.environ.get(name, default)
        if t == "substr":
            # substr(s, start, length) — slice s[start:start+length]; length required
            s = str(args[0]) if args else ""
            start = int(_num(args[1])) if len(args) > 1 else 0
            length = int(_num(args[2])) if len(args) > 2 else max(0, len(s) - start)
            start = max(0, start)
            length = max(0, length)
            return s[start : start + length]
        if t == "sleep":
            ms = int(float(args[0]))
            if ms > 0:
                time.sleep(ms / 1000.0)
            return None
        if t == "filter_high_score":
            # FILTER_HIGH_SCORE <list_var> <min_number> — keep dict-like items with numeric score >= min.
            items = args[0] if args else []
            # IR often passes the list variable name as a string; resolve from frame when present.
            if isinstance(items, str) and isinstance(context, dict) and items in context:
                items = context.get(items)
            if not isinstance(items, list):
                return []
            floor = float(_num(args[1])) if len(args) > 1 else 0.0
            out = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                raw = it.get("score", it.get("relevance", 0))
                try:
                    s = float(raw)
                except (TypeError, ValueError):
                    continue
                if s >= floor:
                    out.append(it)
            return out

        # --- Comparison verbs (EQ/NEQ/GT/LT/GTE/LTE) ---
        # These pass validation in the contract but were missing from the runtime.
        # Purely additive — no existing verb changes.
        if t in ("eq", "equal", "equals"):
            if not args:
                return True
            a, b = args[0], args[1] if len(args) > 1 else None
            # Numeric comparison when both sides look numeric, otherwise string/value equality.
            try:
                return _num(a) == _num(b)
            except Exception:
                return a == b
        if t in ("neq", "ne", "notequal", "not_equal"):
            if not args:
                return False
            a, b = args[0], args[1] if len(args) > 1 else None
            try:
                return _num(a) != _num(b)
            except Exception:
                return a != b
        if t == "gt":
            return _num(args[0]) > _num(args[1]) if len(args) >= 2 else False
        if t == "lt":
            return _num(args[0]) < _num(args[1]) if len(args) >= 2 else False
        if t in ("gte", "ge"):
            return _num(args[0]) >= _num(args[1]) if len(args) >= 2 else False
        if t in ("lte", "le"):
            return _num(args[0]) <= _num(args[1]) if len(args) >= 2 else False

        # --- String predicate verbs ---
        if t == "startswith":
            return str(args[0]).startswith(str(args[1])) if len(args) >= 2 else False
        if t == "endswith":
            return str(args[0]).endswith(str(args[1])) if len(args) >= 2 else False

        # --- Whitespace normalization ---
        # trim: collapse all runs of whitespace to a single space, then strip edges.
        # Eliminates the cascading-REPLACE workaround for HTML-parsed text.
        if t == "trim":
            return re.sub(r"\s+", " ", str(args[0]) if args else "").strip()
        if t == "strip":
            return (str(args[0]) if args else "").strip()
        if t == "lstrip":
            return (str(args[0]) if args else "").lstrip()
        if t == "rstrip":
            return (str(args[0]) if args else "").rstrip()

        # --- Dict introspection ---
        if t == "keys":
            v = args[0] if args else {}
            return list(v.keys()) if isinstance(v, dict) else []
        if t == "values":
            v = args[0] if args else {}
            return list(v.values()) if isinstance(v, dict) else []

        # --- Type coercions ---
        # str/tostring/string: explicit value-to-string (distinct from STRINGIFY which JSON-encodes).
        # Eliminates the `R core.CONCAT "" value ->s` pattern used only for int→str coercion.
        if t in ("str", "tostring", "string"):
            v = args[0] if args else None
            return "" if v is None else str(v)
        if t in ("int", "toint"):
            v = args[0] if args else 0
            if v is None:
                return 0
            return int(_num(v))
        if t in ("float", "tofloat"):
            v = args[0] if args else 0.0
            if v is None:
                return 0.0
            return float(_num(v))
        if t == "bool":
            return bool(args[0]) if args else False

        raise RuntimeError(f"unsupported core builtin target: {t}")
