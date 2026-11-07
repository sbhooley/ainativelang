"""ainl.re.1 matches Python re on the docket, caption, and counsel fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from runtime.bounded_regex import RegexLimitError, regex_contains, regex_findall

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ainl_re_1.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_dialect_matches_python_re_on_the_worker_patterns():
    data = _fixture()
    assert data["dialect"] == "ainl.re.1"
    samples = data["samples"]
    for name, pattern in data["patterns"].items():
        for text in samples:
            theirs = [m.group(0) for m in re.finditer(pattern, text, re.IGNORECASE)]
            ours = regex_findall(text, pattern, "i")
            assert ours == theirs, f"{name} disagreed on {text!r}: {ours!r} vs {theirs!r}"
            assert regex_contains(text, pattern, "i") is bool(theirs)


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
