"""Bounded regular expressions for untrusted document text. Dialect ``ainl.re.1``.

The matcher is a backtracking interpreter with a hard step budget. It is not
Python ``re``. A pattern that would otherwise explode raises instead of
hanging the worker. The graph op turns an input-size or step-limit failure
into an error value so a long filing is a branch, not a dropped document.
Syntax errors still raise: a bad pattern is the author's mistake.

``ainl.re.1`` accepts literals, ``.`` (not newline), ``^`` and ``$`` (``$`` is
the absolute end), ``\\d \\D \\w \\W \\s \\S``, ``\\b``, character classes and
ranges, greedy ``* + ? {n} {n,} {n,m}``, alternation, capturing groups, and
non-capturing ``(?:...)``. ``\\w`` is Unicode: a letter or number
(``str.isalnum``) or ``_``. It is not ``[A-Za-z0-9_]``. ``\\uXXXX`` and
``\\UXXXXXXXX`` are one character, including inside a class. Ignore-case is a
leading ``(?i)`` or a flags argument ``i``. A letter matches when both
characters' ``casefold`` is one code point and those folds are equal. A fold
that changes length is not promised. Replacement text may use ``\\1``. The
pattern may not. ``regex_findall`` returns each full match. It does not
return capturing groups.

Rejected: backreferences, lookahead and lookbehind, named groups, comments,
inline flags other than a leading ``(?i)``, and lazy quantifiers. Caps are
512 pattern characters (the certified counsel expression is 311), 100_000
haystack characters, 100_000 steps, and a quantifier max of 10_000.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

MAX_PATTERN_CHARS = 512
MAX_HAYSTACK_CHARS = 100_000
MAX_STEPS = 100_000
MAX_QUANTIFIER = 10_000


class RegexLimitError(RuntimeError):
    """Pattern, input, or execution exceeded a fixed bound."""


def _bump(steps: List[int]) -> None:
    steps[0] += 1
    if steps[0] > MAX_STEPS:
        raise RegexLimitError("regex step limit")


def _is_word(ch: str) -> bool:
    return bool(ch) and (ch.isalnum() or ch == "_")


class _Parser:
    def __init__(self, pattern: str) -> None:
        self.s = pattern
        self.i = 0
        self.group = 0

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def parse(self) -> Any:
        node = self._alt()
        if self.i != len(self.s):
            raise RegexLimitError("regex syntax error")
        return node

    def _alt(self) -> Any:
        parts = [self._seq()]
        while self.peek() == "|":
            self.i += 1
            parts.append(self._seq())
        if len(parts) == 1:
            return parts[0]
        return ("alt", parts)

    def _seq(self) -> Any:
        items: List[Any] = []
        while self.i < len(self.s) and self.peek() not in ")|":
            items.append(self._quantified())
        if len(items) == 1:
            return items[0]
        return ("seq", items)

    def _quantified(self) -> Any:
        atom = self._atom()
        nxt = self.peek()
        # An empty peek is a substring of every string, so test the character first.
        if nxt and nxt in "*+?{":
            lo, hi = self._quantifier()
            return ("rep", atom, lo, hi)
        return atom

    def _quantifier(self) -> Tuple[int, Optional[int]]:
        ch = self.peek()
        self.i += 1
        if ch == "*":
            return 0, None
        if ch == "+":
            return 1, None
        if ch == "?":
            return 0, 1
        if self.peek() == "}":
            raise RegexLimitError("regex quantifier missing bounds")
        buf = []
        while self.peek() and self.peek() != "}":
            buf.append(self.peek())
            self.i += 1
        if self.peek() != "}":
            raise RegexLimitError("regex quantifier is not closed")
        self.i += 1
        body = "".join(buf)
        if "," in body:
            left, right = body.split(",", 1)
            lo = int(left) if left else 0
            hi: Optional[int] = int(right) if right else None
        else:
            if not body:
                raise RegexLimitError("regex quantifier missing bounds")
            lo = hi = int(body)
        if lo < 0 or (hi is not None and (hi < lo or hi > MAX_QUANTIFIER)):
            raise RegexLimitError("regex quantifier is out of range")
        if hi is None and lo > MAX_QUANTIFIER:
            raise RegexLimitError("regex quantifier is out of range")
        return lo, hi

    def _atom(self) -> Any:
        ch = self.peek()
        if ch == "":
            raise RegexLimitError("regex syntax error")
        if ch == "(":
            self.i += 1
            if self.peek() == "?":
                self.i += 1
                if self.peek() == ":":
                    self.i += 1
                    inner = self._alt()
                    if self.peek() != ")":
                        raise RegexLimitError("regex group is not closed")
                    self.i += 1
                    return inner
                raise RegexLimitError("regex extensions are not allowed")
            self.group += 1
            gid = self.group
            inner = self._alt()
            if self.peek() != ")":
                raise RegexLimitError("regex group is not closed")
            self.i += 1
            return ("group", gid, inner)
        if ch == "[":
            return self._class()
        if ch == "\\":
            self.i += 1
            esc = self.peek()
            if not esc:
                raise RegexLimitError("regex trailing escape")
            if esc in "dDwWsS":
                self.i += 1
                return ("cls", esc)
            if esc == "b":
                self.i += 1
                return ("anchor", "b")
            if esc.isdigit():
                raise RegexLimitError("regex backreferences are not allowed")
            return ("lit", self._after_backslash())
        if ch == ".":
            self.i += 1
            return ("dot",)
        if ch == "^":
            self.i += 1
            return ("anchor", "^")
        if ch == "$":
            self.i += 1
            return ("anchor", "$")
        if ch in "*+?{)|":
            raise RegexLimitError("regex syntax error")
        self.i += 1
        return ("lit", ch)

    def _after_backslash(self) -> str:
        """One escaped character. The backslash is already consumed.

        ``\\u`` plus four hex digits and ``\\U`` plus eight hex digits are
        one code point. Any other letter is that letter, so ``\\-`` is a
        hyphen and ``\\d`` inside a class stays the character ``d``.
        """
        esc = self.peek()
        if not esc:
            raise RegexLimitError("regex trailing escape")
        self.i += 1
        if esc not in ("u", "U"):
            return esc
        width = 4 if esc == "u" else 8
        hexes = self.s[self.i : self.i + width]
        if len(hexes) != width or any(c not in "0123456789abcdefABCDEF" for c in hexes):
            raise RegexLimitError("regex unicode escape is incomplete")
        self.i += width
        code = int(hexes, 16)
        if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
            raise RegexLimitError("regex unicode escape is out of range")
        return chr(code)

    def _class(self) -> Any:
        self.i += 1
        neg = False
        if self.peek() == "^":
            neg = True
            self.i += 1
        chars: List[str] = []
        ranges: List[Tuple[str, str]] = []
        if self.peek() == "]":
            chars.append("]")
            self.i += 1
        while self.peek() and self.peek() != "]":
            a = self.peek()
            self.i += 1
            if a == "\\" and self.peek():
                a = self._after_backslash()
            if self.peek() == "-" and self.s[self.i + 1 : self.i + 2] not in ("", "]"):
                self.i += 1
                b = self.peek()
                if not b:
                    raise RegexLimitError("regex class is not closed")
                self.i += 1
                if b == "\\" and self.peek():
                    b = self._after_backslash()
                ranges.append((a, b))
            else:
                chars.append(a)
        if self.peek() != "]":
            raise RegexLimitError("regex class is not closed")
        self.i += 1
        return ("set", neg, chars, ranges)


def compile_pattern(pattern: str) -> Any:
    if not isinstance(pattern, str):
        pattern = "" if pattern is None else str(pattern)
    if pattern == "":
        raise RegexLimitError("regex pattern must not be empty")
        if len(pattern) > MAX_PATTERN_CHARS:
            raise RegexLimitError(f"regex pattern exceeds {MAX_PATTERN_CHARS} characters")
    return _Parser(pattern).parse()


def _class_hit(kind: str, ch: str) -> bool:
    if kind == "d":
        return ch.isdigit()
    if kind == "D":
        return not ch.isdigit()
    if kind == "w":
        return _is_word(ch)
    if kind == "W":
        return not _is_word(ch)
    if kind == "s":
        return ch.isspace()
    if kind == "S":
        return not ch.isspace()
    return False


def _set_hit(
    neg: bool,
    chars: List[str],
    ranges: List[Tuple[str, str]],
    ch: str,
    *,
    ignorecase: bool = False,
) -> bool:
    def one(candidate: str) -> bool:
        return candidate in chars or any(a <= candidate <= b for a, b in ranges)

    if ignorecase:
        folded = {ch, ch.lower(), ch.upper()}
        cf = ch.casefold()
        if len(cf) == 1:
            folded.add(cf)
        hit = any(one(candidate) for candidate in folded)
    else:
        hit = one(ch)
    return (not hit) if neg else hit


def prepare_pattern(pattern: str, flags: Any = None) -> Tuple[str, bool]:
    """Return the pattern body and whether matching is case-insensitive."""
    text = pattern
    ignore = False
    while text.startswith("(?i)"):
        ignore = True
        text = text[4:]
    flag = "" if flags is None else str(flags).strip().lower()
    if flags is True or flag in {"i", "ignorecase"}:
        ignore = True
    return text, ignore


def limit_error_value(exc: BaseException) -> Optional[dict]:
    """An error value for a size or step limit. Syntax errors return None.

    The message does not include the haystack.
    """
    if not isinstance(exc, RegexLimitError):
        return None
    text = str(exc)
    if "input exceeds" in text:
        return {
            "error": {
                "code": "REGEX_INPUT_LIMIT",
                "message": "regex input exceeds 100000 characters",
            }
        }
    if "step limit" in text:
        return {"error": {"code": "REGEX_STEP_LIMIT", "message": "regex step limit"}}
    return None


class _Engine:
    def __init__(self, text: str, *, ignorecase: bool = False) -> None:
        if len(text) > MAX_HAYSTACK_CHARS:
            raise RegexLimitError("regex input exceeds 100000 characters")
        self.text = text
        self.ignorecase = bool(ignorecase)
        self.steps = [0]
        self.groups: List[Tuple[int, int]] = []

    def match_at(self, node: Any, i: int) -> Optional[int]:
        self.groups = []
        found: List[int] = []

        def done(end: int) -> bool:
            found.append(end)
            return True

        if self._run(node, i, done):
            return found[0]
        return None

    def _run(self, node: Any, i: int, cont) -> bool:
        """Try node at i. On a match, call cont(end). Cont returns whether the rest matched.

        The step counter is not rewound. A pattern that retries until the
        budget is gone raises instead of hanging.
        """
        _bump(self.steps)
        kind = node[0]
        if kind == "seq":
            parts = node[1]

            def go(k: int, pos: int) -> bool:
                if k == len(parts):
                    return cont(pos)
                return self._run(parts[k], pos, lambda nxt, k=k: go(k + 1, nxt))

            return go(0, i)
        if kind == "alt":
            saved = list(self.groups)
            for part in node[1]:
                self.groups = list(saved)
                if self._run(part, i, cont):
                    return True
            self.groups = saved
            return False
        if kind == "lit":
            if i >= len(self.text):
                return False
            here = self.text[i]
            want = node[1]
            if self.ignorecase:
                left = here.casefold()
                right = want.casefold()
                if len(left) == 1 and len(right) == 1 and left == right:
                    return cont(i + 1)
                return False
            if here == want:
                return cont(i + 1)
            return False
        if kind == "dot":
            if i < len(self.text) and self.text[i] != "\n":
                return cont(i + 1)
            return False
        if kind == "cls":
            if i < len(self.text) and _class_hit(node[1], self.text[i]):
                return cont(i + 1)
            return False
        if kind == "set":
            if i < len(self.text) and _set_hit(
                node[1], node[2], node[3], self.text[i], ignorecase=self.ignorecase
            ):
                return cont(i + 1)
            return False
        if kind == "anchor":
            which = node[1]
            if which == "^":
                return cont(i) if i == 0 else False
            if which == "$":
                return cont(i) if i == len(self.text) else False
            prev = self.text[i - 1] if i > 0 else ""
            nxtc = self.text[i] if i < len(self.text) else ""
            return cont(i) if _is_word(prev) != _is_word(nxtc) else False
        if kind == "group":
            gid = node[1]
            start = i
            saved = list(self.groups)

            def after(nxt: int, start: int = start, gid: int = gid) -> bool:
                while len(self.groups) < gid:
                    self.groups.append((-1, -1))
                self.groups[gid - 1] = (start, nxt)
                return cont(nxt)

            if self._run(node[2], i, after):
                return True
            self.groups = saved
            return False
        if kind == "rep":
            return self._rep(node[1], node[2], node[3], i, 0, cont)
        raise RegexLimitError("regex syntax error")

    def _rep(self, atom: Any, lo: int, hi: Optional[int], i: int, taken: int, cont) -> bool:
        _bump(self.steps)
        if hi is None or taken < hi:
            saved = list(self.groups)

            def after_one(nxt: int, i: int = i, taken: int = taken) -> bool:
                if nxt == i:
                    return False
                return self._rep(atom, lo, hi, nxt, taken + 1, cont)

            if self._run(atom, i, after_one):
                return True
            self.groups = saved
        if taken >= lo:
            return cont(i)
        return False


def _search(
    pattern: str, text: str, flags: Any = None
) -> List[Tuple[int, int, List[Tuple[int, int]]]]:
    raw = "" if pattern is None else str(pattern)
    if len(raw) > MAX_PATTERN_CHARS:
        raise RegexLimitError(f"regex pattern exceeds {MAX_PATTERN_CHARS} characters")
    body, ignore = prepare_pattern(raw, flags)
    node = compile_pattern(body)
    eng = _Engine(text, ignorecase=ignore)
    found: List[Tuple[int, int, List[Tuple[int, int]]]] = []
    i = 0
    n = len(text)
    while i <= n:
        eng.steps[0] = 0
        end = eng.match_at(node, i)
        if end is not None and end >= i:
            found.append((i, end, list(eng.groups)))
            if end == i:
                i += 1
            else:
                i = end
            if i > n:
                break
            continue
        if i == n:
            break
        i += 1
    return found


def regex_contains(hay: Any, pattern: Any, flags: Any = None) -> bool:
    text = "" if hay is None else str(hay)
    return bool(_search(str(pattern), text, flags))


def regex_findall(hay: Any, pattern: Any, flags: Any = None) -> List[str]:
    text = "" if hay is None else str(hay)
    return [text[a:b] for a, b, _groups in _search(str(pattern), text, flags)]


def _apply_repl(repl: str, text: str, groups: List[Tuple[int, int]]) -> str:
    if len(repl) > 10_000:
        raise RegexLimitError("regex replacement exceeds 10000 characters")
    out: List[str] = []
    i = 0
    while i < len(repl):
        if repl[i] == "\\" and i + 1 < len(repl):
            nxt = repl[i + 1]
            if nxt.isdigit() and nxt != "0":
                idx = int(nxt) - 1
                if 0 <= idx < len(groups) and groups[idx][0] >= 0:
                    a, b = groups[idx]
                    out.append(text[a:b])
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(repl[i])
        i += 1
    return "".join(out)


def regex_replace(hay: Any, pattern: Any, repl: Any, flags: Any = None) -> str:
    text = "" if hay is None else str(hay)
    replacement = "" if repl is None else str(repl)
    pieces: List[str] = []
    cursor = 0
    for a, b, groups in _search(str(pattern), text, flags):
        pieces.append(text[cursor:a])
        pieces.append(_apply_repl(replacement, text, groups))
        cursor = b
    pieces.append(text[cursor:])
    return "".join(pieces)
