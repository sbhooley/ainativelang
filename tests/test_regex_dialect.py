"""ainl.re.1 matches Python re on the docket, caption, and counsel fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from runtime.bounded_regex import (
    RegexLimitError,
    regex_contains,
    regex_findall,
    regex_replace,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ainl_re_1.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_dialect_matches_python_re_on_the_worker_patterns():
    data = _fixture()
    assert data["dialect"] == "ainl.re.1"
    flags = data["flags"]
    assert flags["caption"] == ""
    assert flags["counsel"] == "i"
    assert flags["docket"] == "i"
    assert flags["docket_short"] == "i"
    samples = data["samples"]
    for name, pattern in data["patterns"].items():
        ignore = flags[name] == "i"
        py_flag = re.IGNORECASE if ignore else 0
        ours_flag = "i" if ignore else None
        for text in samples:
            theirs = [m.group(0) for m in re.finditer(pattern, text, py_flag)]
            ours = regex_findall(text, pattern, ours_flag)
            assert ours == theirs, f"{name} disagreed on {text!r}: {ours!r} vs {theirs!r}"
            assert regex_contains(text, pattern, ours_flag) is bool(theirs)


def test_dialect_rejects_extensions_python_re_would_accept():
    with pytest.raises(RegexLimitError):
        regex_contains("aa", r"(a)\1")
    with pytest.raises(RegexLimitError):
        regex_contains("a", "(?=a)")
    with pytest.raises(RegexLimitError):
        regex_contains("a", "(?P<name>a)")


def test_docket_pattern_is_the_worker_expression():
    pattern = _fixture()["patterns"]["docket"]
    assert pattern == (
        r"\b(?:\d{1,2}:\d{2}-(?:cv|cr|mc|md)-\d{3,6}|No\.\s*\d{2,4}-[A-Za-z0-9\-]{2,12})\b"
    )


def test_caption_and_counsel_are_the_worker_expressions():
    patterns = _fixture()["patterns"]
    caption = (
        r"\b([A-Z][A-Za-z0-9.&'\-]+(?:\s+[A-Z][A-Za-z0-9.&'\-]+){0,4})"
        r"\s+v\.\s+"
        r"([A-Z][A-Za-z0-9.&'\-]+(?:\s+[A-Z][A-Za-z0-9.&'\-]+){0,5})\b"
    )
    counsel = (
        r"First\s+Liberty(?:\s+Institute)?(?:\s+\w+){0,8}\s+"
        r"(?:represented|represents|representing|filed|settled|counsel|attorneys|lawyers)"
        r"|(?:represented|represents|representing|filed|settled)\s+by\s+"
        r"First\s+Liberty(?:\s+Institute)?"
        r"|(?:counsel|attorneys|lawyers)\s+(?:with|from|at|for)\s+"
        r"First\s+Liberty(?:\s+Institute)?"
    )
    assert patterns["caption"] == caption
    assert patterns["counsel"] == counsel
    assert len(counsel) == 311
    assert regex_findall("Smith v. Jones", caption) == ["Smith v. Jones"]
    assert regex_findall("smith v. jones", caption) == []
    assert regex_findall("SMITH V JONES", caption) == []
    assert [m.group(0) for m in re.finditer(caption, "smith v. jones")] == []
    assert [m.group(0) for m in re.finditer(caption, "smith v. jones", re.I)] == [
        "smith v. jones"
    ]
    filed = "First Liberty Institute lawyers filed the brief"
    assert regex_findall(filed, counsel, "i") == [m.group(0) for m in re.finditer(counsel, filed, re.I)]
    naive = "First Liberty naïve represented the client"
    assert regex_contains(naive, counsel, "i") is bool(re.search(counsel, naive, re.I))


def test_findall_returns_the_full_hashtag_and_replace_can_drop_the_mark():
    pattern = _fixture()["patterns"]["hashtag"]
    assert pattern == r"#([A-Za-z][A-Za-z0-9_]{1,50})"
    text = "see #ReligiousLiberty today"
    assert regex_findall(text, pattern) == ["#ReligiousLiberty"]
    assert regex_findall(text, pattern) == [m.group(0) for m in re.finditer(pattern, text)]
    assert regex_replace(text, pattern, r"\1") == re.sub(pattern, r"\1", text)


def test_unicode_escapes_in_a_class_match_python_re():
    pattern = _fixture()["patterns"]["nonlatin"]
    assert r"\u0400" in pattern
    assert regex_findall("Я中אاअA", pattern) == ["Я", "中", "א", "ا", "अ"]
    assert regex_findall("Я", pattern) == [m.group(0) for m in re.finditer(pattern, "Я")]


def test_short_docket_is_not_the_any_digit_flag():
    patterns = _fixture()["patterns"]
    assert patterns["docket_short"] == r"\b\d:\d{2}-cv-\d+\b"
    assert "docket" in patterns and patterns["docket"] != patterns["docket_short"]
    assert regex_findall("1:26-cv-12", patterns["docket_short"], "i") == ["1:26-cv-12"]
    assert regex_findall("1:26-cv-12", patterns["docket"], "i") == []


def test_word_class_is_unicode():
    assert regex_contains("Я", r"\w")
    assert regex_contains("é", r"\w")
    assert not regex_contains("-", r"\w")
    assert regex_contains("Я", r"\w") is bool(re.search(r"\w", "Я"))
