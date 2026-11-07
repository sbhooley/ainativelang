"""Pure decision helpers shared by the R adapter.

These ops sit beside the 1.8.1 behavior of ``EQ``, ``CONTAINS``, and ``TRIM``.
They do not replace those ops. Equality here does not coerce, an empty needle
does not match, and format strings cannot read object attributes.
"""

from __future__ import annotations

import html
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence

from runtime.bounded_regex import regex_contains, regex_findall, regex_replace
from runtime.values import truthy

_EN_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Defense in depth under the allowlist. `_` is a word character, so a bare
# ``\bsas\b`` misses ``SAS_TOKEN``. A name the allowlist forgot still has to
# look nothing like a key.
_SECRET_ENV = re.compile(
    r"(secret|password|passwd|token|api[-_]?key|credential|private[-_]?key|"
    r"client[-_]?secret|connection[-_]?string|account[-_]?key|access[-_]?key|"
    r"(?:^|_)sas(?:$|_)|(?:^|_)key$)",
    re.IGNORECASE,
)

_FORMAT_FIELD = re.compile(r"\{([^{}]*)\}")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def strict_eq(a: Any, b: Any) -> bool:
    """Equality with no string/bool/number coercion.

    ``True`` is not ``1``. ``\"1\"`` is not ``1``. Two numbers still compare
    equal across ``int`` and ``float`` (``1`` equals ``1.0``).
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    return type(a) is type(b) and a == b


def has_text(hay: Any, needle: Any) -> bool:
    """Substring test that is false for an empty needle."""
    n = "" if needle is None else str(needle)
    if n == "":
        return False
    h = "" if hay is None else str(hay)
    return n in h


def _word_chars(s: str) -> List[str]:
    words: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if not buf:
            return
        token = "".join(buf).strip("-")
        buf.clear()
        if token:
            words.append(token.casefold())

    for ch in s:
        if ch.isalnum() or ch == "-":
            buf.append(ch)
        else:
            flush()
    flush()
    return words


def contains_word(hay: Any, needle: Any) -> bool:
    """Contiguous word-sequence match.

    Letters and digits are word characters. An ASCII hyphen stays inside a
    word (``pre-litigation``). Every other character is a boundary, so
    ``Smith, Jones`` contains the words ``smith`` and ``jones``. An empty
    needle does not match. Matching is case-insensitive via ``casefold``.
    """
    nw = _word_chars("" if needle is None else str(needle))
    if not nw:
        return False
    hw = _word_chars("" if hay is None else str(hay))
    n = len(nw)
    if n > len(hw):
        return False
    for i in range(len(hw) - n + 1):
        if hw[i : i + n] == nw:
            return True
    return False


def replace_chars(hay: Any, charset: Any, repl: Any) -> str:
    """Replace every character in ``charset`` with ``repl`` (possibly empty)."""
    text = "" if hay is None else str(hay)
    chars = set("" if charset is None else str(charset))
    if not chars:
        return text
    piece = "" if repl is None else str(repl)
    return "".join(piece if ch in chars else ch for ch in text)


def in_collection(needle: Any, collection: Any) -> bool:
    """Exact membership. A string collection matches only the whole string."""
    if isinstance(collection, dict):
        return any(strict_eq(needle, key) for key in collection.keys())
    if isinstance(collection, (list, tuple, set, frozenset)):
        return any(strict_eq(needle, item) for item in collection)
    if isinstance(collection, str):
        return isinstance(needle, str) and needle == collection
    return False


def casefold_text(value: Any) -> str:
    return ("" if value is None else str(value)).casefold()


def normalize_text(value: Any, form: Any = "NFC") -> str:
    name = str(form or "NFC").upper()
    if name not in {"NFC", "NFKC"}:
        raise RuntimeError("normalize form must be NFC or NFKC")
    return unicodedata.normalize(name, "" if value is None else str(value))


def html_text(value: Any) -> str:
    """Strip tags and collapse whitespace. This is not a sanitizer.

    A nested tag such as ``<scr<script>ipt>`` survives a stripper. Do not
    render the result. Collectors that need feeds, links, or encodings stay
    in Python with a real parser.
    """
    raw = "" if value is None else str(value)
    if len(raw) > 1_000_000:
        raise RuntimeError("html input exceeds 1000000 characters")
    without = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", raw)
    without = re.sub(r"(?s)<[^>]*>", " ", without)
    without = html.unescape(without)
    return re.sub(r"\s+", " ", without).strip()


def is_error_value(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    err = value.get("error")
    return isinstance(err, dict) and bool(err.get("code"))


def env_name_is_secret(name: str) -> bool:
    return bool(_SECRET_ENV.search(name or ""))


def read_env(name: str, allowlist: Any, default: Any = None) -> Any:
    """Read one environment name. Default deny. Secrets never match.

    The allowlist is a host limit. A graph cannot put a name on it. An
    allowlisted name that still looks like a key is refused, and the value
    is not in the error.
    """
    if not name:
        return None
    if env_name_is_secret(name):
        raise RuntimeError("core.ENV cannot read a secret")
    allowed = {str(item) for item in allowlist} if isinstance(allowlist, (list, tuple, set)) else set()
    if name not in allowed:
        raise RuntimeError("core.ENV name is not allowlisted")
    return os.environ.get(name, default)


def _plural_word(value: Any, spec: str) -> str:
    forms = spec.split("|")
    if len(forms) != 2 or not forms[0] or not forms[1]:
        raise RuntimeError("plural format needs singular|plural")
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    return forms[0] if n == 1 else forms[1]


def safe_format(template: Any, values: Sequence[Any]) -> str:
    """Tiny template. ``{0}``, ``{}``, ``{name}`` on one dict, and ``{n:plural:a|b}``.

    Dots, indexing, conversions, and dunder names are rejected so a format
    string cannot read object attributes.
    """
    text = "" if template is None else str(template)
    if len(text) > 10_000:
        raise RuntimeError("format template exceeds 10000 characters")
    auto = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal auto
        body = match.group(1)
        if any(tok in body for tok in (".", "[", "]", "!", "__")):
            raise RuntimeError("format field access is not allowed")
        name, spec = body, ""
        if ":" in body:
            name, spec = body.split(":", 1)
        if name == "":
            if auto >= len(values):
                raise RuntimeError("format field missing")
            val = values[auto]
            auto += 1
        elif name.isdigit():
            idx = int(name)
            if idx < 0 or idx >= len(values):
                raise RuntimeError("format field missing")
            val = values[idx]
        else:
            if not _NAME.fullmatch(name):
                raise RuntimeError("format field name is not allowed")
            if len(values) == 1 and isinstance(values[0], dict) and name in values[0]:
                val = values[0][name]
            else:
                raise RuntimeError("format field missing")
        if spec.startswith("plural:"):
            return _plural_word(val, spec[len("plural:") :])
        if spec:
            raise RuntimeError("format spec is not allowed")
        return "" if val is None else str(val)

    return _FORMAT_FIELD.sub(repl, text)


def _parse_english_date(text: str) -> Optional[datetime]:
    m = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        text.strip(),
    )
    if not m:
        return None
    month = _EN_MONTHS.get(m.group(1).casefold())
    if not month:
        return None
    day = int(m.group(2))
    year = int(m.group(3))
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_with_format(text: str, fmt: str) -> Optional[datetime]:
    """Locale-free ``strptime`` subset: ``%Y %m %d %H %M %S`` and literals."""
    if len(fmt) > 64 or any(tok in fmt for tok in ("%B", "%b", "%A", "%a", "%c", "%x", "%X", "%p")):
        return None
    i = 0
    j = 0
    parts = {"Y": 1970, "m": 1, "d": 1, "H": 0, "M": 0, "S": 0}
    seen = set()
    while i < len(fmt):
        if fmt[i] == "%" and i + 1 < len(fmt):
            code = fmt[i + 1]
            i += 2
            if code not in parts or code in seen:
                return None
            width = 4 if code == "Y" else 2
            if j + width > len(text) or not text[j : j + width].isdigit():
                # %m and friends may be unpadded in the explicit English path only.
                if code == "Y" or j >= len(text) or not text[j].isdigit():
                    return None
                k = j
                while k < len(text) and text[k].isdigit() and k - j < width:
                    k += 1
                if k == j:
                    return None
                parts[code] = int(text[j:k])
                j = k
            else:
                parts[code] = int(text[j : j + width])
                j += width
            seen.add(code)
            continue
        if j >= len(text) or text[j] != fmt[i]:
            return None
        j += 1
        i += 1
    if j != len(text) or "Y" not in seen:
        return None
    try:
        return datetime(
            parts["Y"], parts["m"], parts["d"], parts["H"], parts["M"], parts["S"], tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_time(text: Any, formats: Any = None) -> Optional[int]:
    """UTC unix seconds, or None. No ambient locale.

    Accepts ISO-8601, including fractional seconds and numeric offsets such
    as ``-05:00``. Fractional seconds are truncated, not rounded. A value
    with no offset is UTC. English dates accept ``November 7, 2026`` and
    ``Nov 7, 2026``. A second argument is an explicit format string or a
    list of them, using only ``%Y %m %d %H %M %S`` and literal characters.
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw or len(raw) > 80:
        return None
    iso = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        dt = None
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    english = _parse_english_date(raw)
    if english is not None and not formats:
        return int(english.timestamp())
    fmts: List[str]
    if formats is None:
        fmts = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"]
    elif isinstance(formats, str):
        fmts = [formats]
    elif isinstance(formats, list):
        fmts = [str(x) for x in formats[:8]]
    else:
        return None
    for fmt in fmts:
        parsed = _parse_with_format(raw, fmt)
        if parsed is not None:
            return int(parsed.timestamp())
    if english is not None:
        return int(english.timestamp())
    return None


def add_days(unix_seconds: Any, days: Any) -> int:
    """Add elapsed UTC seconds: ``days * 86400``.

    This is not a civil calendar add. ``PARSE_TIME`` treats a naive value as
    UTC and converts a numeric offset to UTC before this runs. Across a DST
    boundary, the same local wall time is a different number of seconds. A
    stored local clock without an offset stays in the host.
    """
    base = int(unix_seconds)
    delta = int(days)
    if abs(delta) > 36600:
        raise RuntimeError("add_days exceeds 36600 days")
    return base + delta * 86400


def before(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    try:
        return int(a) < int(b)
    except (TypeError, ValueError):
        return False


def bool_and(a: Any, b: Any) -> bool:
    return truthy(a) and truthy(b)


def bool_or(a: Any, b: Any) -> bool:
    return truthy(a) or truthy(b)


def bool_not(a: Any) -> bool:
    return not truthy(a)


__all__ = [
    "add_days",
    "before",
    "bool_and",
    "bool_not",
    "bool_or",
    "casefold_text",
    "contains_word",
    "env_name_is_secret",
    "has_text",
    "html_text",
    "in_collection",
    "is_error_value",
    "normalize_text",
    "parse_time",
    "regex_contains",
    "regex_findall",
    "regex_replace",
    "replace_chars",
    "safe_format",
    "strict_eq",
]
