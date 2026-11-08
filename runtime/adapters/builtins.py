from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
import uuid as uuid_mod
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter
from runtime.decision_ops import (
    add_days,
    before,
    bool_and,
    bool_not,
    bool_or,
    casefold_text,
    contains_word,
    read_env,
    has_text,
    html_text,
    in_collection,
    is_error_value,
    normalize_text,
    parse_time,
    regex_contains,
    regex_findall,
    regex_replace,
    replace_chars,
    safe_format,
    strict_eq,
)
from runtime.bounded_regex import limit_error_value
from runtime.extract_doc import extract_document
from runtime.firm_contract import apply_shape, untrusted_prompt
from runtime.values import coerce_number, deep_get, deep_put, stable_sort, truthy


def _stamped_now(context: Any) -> int:
    if isinstance(context, dict) and context.get("_now") is not None:
        return int(context["_now"])
    return int(time.time())


def _regex_value(fn: Any, *args: Any) -> Any:
    """Size and step limits become error values. Syntax errors still raise."""
    try:
        return fn(*args)
    except Exception as exc:
        value = limit_error_value(exc)
        if value is None:
            raise
        return value


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
      abs/ceil/floor/round/pow/mod — numeric ops
      and/or/not — boolean ops using truthy(); noop — returns None
      eqs — strict equality (True is not 1, "1" is not 1). eq still coerces.
      has — substring, false when the needle is empty. contains stays true.
      contains_word / replace_chars / in — word, charset, and exact membership
      regex_contains / regex_replace / regex_findall — bounded, no backreferences
      parse_time / add_days / before — UTC calendar helpers, no locale
      casefold / normalize (NFC, NFKC) / html_text / is_error
      if — value select, no control transfer
      push / put — list append and nested field write (copy)
      hash(s, algo?) / uuid() — hashing and id generation
      sort/reverse/flatten/unique — list ops. sort(list, key) is stable by field.
      type(v) — type name; format — {0}, {}, {name}, {n:plural:a|b}; no attribute access
      range(stop|start,stop[,step]) — list of ints
      pick(dict, keys...) / omit(dict, keys...) — key projection
      zip(list...) — pairwise grouping truncated to shortest input
    map / filter / reduce run in the engine over a same-file label, not here.
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
            return _stamped_now(context)
        if t == "iso":
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_stamped_now(context)))
        if t == "iso_ts":
            ts = int(_num(args[0])) if args else _stamped_now(context)
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        if t in ("echo", "id"):
            return args[0] if args else None
        if t == "env":
            # Default deny. The host allowlist is stamped on the call context
            # by the engine. A frame key of the same name does not widen it.
            name = str(args[0]) if args else ""
            default = None if len(args) < 2 else args[1]
            allow: Any = []
            if isinstance(context, dict):
                raw_allow = context.get("_env_allowlist")
                if isinstance(raw_allow, (list, tuple, set)):
                    allow = raw_allow
            return read_env(name, allow, default)
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
            # Numeric coercion is the 1.8.1 behavior. "1", 1, 1.0, and True compare
            # equal. "yes" falls through to == when float() fails. Use eqs to opt out.
            try:
                return _num(a) == _num(b)
            except Exception:
                return a == b
        if t == "eqs":
            if len(args) < 2:
                return False
            return strict_eq(args[0], args[1])
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

        if t == "abs":
            return abs(_num(args[0]))
        if t == "ceil":
            return math.ceil(_num(args[0]))
        if t == "floor":
            return math.floor(_num(args[0]))
        if t == "round":
            v = _num(args[0])
            ndigits = int(_num(args[1])) if len(args) > 1 else 0
            return round(v, ndigits)
        if t == "pow":
            return _num(args[0]) ** _num(args[1])
        if t == "mod":
            return _num(args[0]) % _num(args[1])
        if t == "and":
            if len(args) >= 2:
                return bool_and(args[0], args[1])
            return bool_and(args[0], False) if args else False
        if t == "or":
            if len(args) >= 2:
                return bool_or(args[0], args[1])
            return bool_or(args[0], False) if args else False
        if t == "not":
            return bool_not(args[0]) if args else True
        if t == "if":
            cond = args[0] if args else False
            then_v = args[1] if len(args) > 1 else None
            else_v = args[2] if len(args) > 2 else None
            return then_v if truthy(cond) else else_v
        if t == "noop":
            return None
        if t == "uuid":
            return str(uuid_mod.uuid4())
        if t == "hash":
            s = str(args[0]) if args else ""
            algo = str(args[1]).lower() if len(args) > 1 else "sha256"
            h = hashlib.new(algo)
            h.update(s.encode("utf-8"))
            return h.hexdigest()
        if t == "sort":
            arr = args[0] if args else []
            if len(args) > 1 and isinstance(arr, list):
                desc = len(args) > 2 and args[2] is True
                return stable_sort(list(arr), str(args[1]), desc=desc)
            if not isinstance(arr, list):
                arr = list(str(arr))
            return sorted(arr, key=lambda x: str(x))
        if t == "reverse":
            arr = args[0] if args else []
            if isinstance(arr, list):
                return list(reversed(arr))
            return list(reversed(list(str(arr))))
        if t == "flatten":
            arr = args[0] if args else []
            if not isinstance(arr, list):
                return [arr]
            out: List[Any] = []
            for item in arr:
                if isinstance(item, list):
                    out.extend(item)
                else:
                    out.append(item)
            return out
        if t == "unique":
            arr = args[0] if args else []
            if not isinstance(arr, list):
                return [arr]
            seen: set = set()
            out_u: List[Any] = []
            for item in arr:
                key = json.dumps(item, sort_keys=True, default=str) if isinstance(item, (dict, list)) else item
                if key in seen:
                    continue
                seen.add(key)
                out_u.append(item)
            return out_u
        if t == "type":
            v = args[0] if args else None
            if v is None:
                return "null"
            if isinstance(v, bool):
                return "bool"
            if isinstance(v, int):
                return "int"
            if isinstance(v, float):
                return "float"
            if isinstance(v, str):
                return "string"
            if isinstance(v, list):
                return "list"
            if isinstance(v, dict):
                return "dict"
            return type(v).__name__
        if t == "format":
            # {0}, {}, {name} on a single dict, and {n:plural:one|many}.
            # Attribute access ({0.__class__}) is rejected.
            template = args[0] if args else ""
            return safe_format(template, args[1:])
        if t == "range":
            # range(stop) | range(start, stop) | range(start, stop, step) — returns a list of ints.
            nums = [int(_num(a)) for a in args[:3]]
            if not nums:
                return []
            return list(range(*nums))
        if t in ("pick", "omit"):
            # pick(dict, keys...) / omit(dict, keys...) — keys as varargs or a single list arg.
            src = args[0] if args else {}
            if not isinstance(src, dict):
                return {}
            raw_keys = args[1:]
            if len(raw_keys) == 1 and isinstance(raw_keys[0], list):
                raw_keys = raw_keys[0]
            keys = {str(k) for k in raw_keys}
            if t == "pick":
                return {k: v for k, v in src.items() if k in keys}
            return {k: v for k, v in src.items() if k not in keys}
        if t == "zip":
            # zip(list1, list2, ...) — list of pair/tuple lists, truncated to the shortest input.
            lists = [a for a in args if isinstance(a, list)]
            if not lists:
                return []
            return [list(group) for group in zip(*lists)]
        if t == "slice":
            # slice(list_or_str, start, end?) — Python-style [start:end]; end omitted = to end.
            seq = args[0] if args else []
            if not isinstance(seq, (list, str)):
                seq = str(seq)
            start = int(_num(args[1])) if len(args) > 1 else 0
            end = int(_num(args[2])) if len(args) > 2 else None
            return seq[start:end]
        if t == "has":
            return has_text(args[0] if args else "", args[1] if len(args) > 1 else "")
        if t == "contains_word":
            return contains_word(args[0] if args else "", args[1] if len(args) > 1 else "")
        if t == "replace_chars":
            return replace_chars(
                args[0] if args else "",
                args[1] if len(args) > 1 else "",
                args[2] if len(args) > 2 else "",
            )
        if t == "in":
            return in_collection(args[0] if args else None, args[1] if len(args) > 1 else None)
        if t == "regex_contains":
            return _regex_value(
                regex_contains,
                args[0] if args else "",
                args[1] if len(args) > 1 else "",
                args[2] if len(args) > 2 else None,
            )
        if t == "regex_replace":
            return _regex_value(
                regex_replace,
                args[0] if args else "",
                args[1] if len(args) > 1 else "",
                args[2] if len(args) > 2 else "",
                args[3] if len(args) > 3 else None,
            )
        if t == "regex_findall":
            return _regex_value(
                regex_findall,
                args[0] if args else "",
                args[1] if len(args) > 1 else "",
                args[2] if len(args) > 2 else None,
            )
        if t == "parse_time":
            raw = args[0] if args else None
            if isinstance(raw, str) and raw.strip().lower() == "now":
                return _stamped_now(context)
            return parse_time(raw, args[1] if len(args) > 1 else None)
        if t == "untrusted_prompt":
            return untrusted_prompt(args[0] if args else "", args[1] if len(args) > 1 else "")
        if t == "shape":
            return apply_shape(args[0] if args else None, args[1:])
        if t == "add_days":
            return add_days(args[0] if args else 0, args[1] if len(args) > 1 else 0)
        if t == "before":
            return before(args[0] if args else None, args[1] if len(args) > 1 else None)
        if t == "casefold":
            return casefold_text(args[0] if args else "")
        if t == "normalize":
            return normalize_text(args[0] if args else "", args[1] if len(args) > 1 else "NFC")
        if t == "html_text":
            return html_text(args[0] if args else "")
        if t == "extract":
            return extract_document(
                args[0] if args else "",
                args[1] if len(args) > 1 else "auto",
            )
        if t == "is_error":
            return is_error_value(args[0] if args else None)
        if t == "push":
            arr = list(args[0]) if args and isinstance(args[0], list) else []
            if len(args) > 1:
                arr.append(args[1])
            return arr
        if t == "put":
            src = args[0] if args and isinstance(args[0], dict) else {}
            src = copy.deepcopy(src)
            path = str(args[1]) if len(args) > 1 else ""
            value = args[2] if len(args) > 2 else None
            return deep_put(src, path, value)
        if t in ("map", "filter", "reduce"):
            raise RuntimeError(f"core.{t} is evaluated by the runtime over a label")

        raise RuntimeError(f"unsupported core builtin target: {t}")
