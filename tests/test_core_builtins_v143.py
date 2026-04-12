"""
Regression coverage for v1.4.3+ ``core.*`` comparison, string, coercion, and dict verbs.
"""
from __future__ import annotations

import pytest

from runtime.adapters.builtins import CoreBuiltinAdapter

pytestmark = pytest.mark.usefixtures("offline_llm_provider_config")


@pytest.fixture
def core():
    return CoreBuiltinAdapter()


@pytest.mark.parametrize(
    "target,args,expected",
    [
        ("eq", [1, 1], True),
        ("eq", [1, "1"], True),
        ("eq", ["a", "a"], True),
        ("eq", [1, 2], False),
        ("neq", [1, 2], True),
        ("neq", [1, 1], False),
        ("gt", [2, 1], True),
        ("gt", [1, 2], False),
        ("lt", [1, 2], True),
        ("lt", [2, 1], False),
        ("gte", [2, 2], True),
        ("gte", [2, 3], False),
        ("lte", [2, 2], True),
        ("lte", [3, 2], False),
    ],
)
def test_comparison_ops_happy_path(core: CoreBuiltinAdapter, target, args, expected):
    assert core.call(target, args, {}) is expected


@pytest.mark.parametrize("target", ["gt", "lt"])
def test_comparison_equal_values_strictly_false(core: CoreBuiltinAdapter, target: str):
    assert core.call(target, [3, 3], {}) is False


@pytest.mark.parametrize(
    "target,args",
    [
        ("gt", ["x", "y"]),
        ("lt", ["x", "y"]),
        ("gte", ["a", 1]),
    ],
)
def test_comparison_non_numeric_raises_value_error(core: CoreBuiltinAdapter, target, args):
    with pytest.raises(ValueError):
        core.call(target, args, {})


def test_eq_falls_back_to_equality_when_not_numeric(core: CoreBuiltinAdapter):
    """Non-numeric ``EQ`` falls back to Python equality after failed numeric parse."""
    assert core.call("eq", ["a", "b"], {}) is False


@pytest.mark.parametrize(
    "target,arg,expected",
    [
        ("trim", "  hello   world  ", "hello world"),
        ("trim", "\tfoo\n\nbar\t", "foo bar"),
        ("strip", "  padded  ", "padded"),
        ("strip", "\nleft", "left"),
        ("strip", "right\t", "right"),
    ],
)
def test_trim_strip_whitespace(core: CoreBuiltinAdapter, target, arg, expected):
    assert core.call(target, [arg], {}) == expected


@pytest.mark.parametrize(
    "target,hay,needle,expected",
    [
        ("startswith", "abcdef", "abc", True),
        ("startswith", "abcdef", "abx", False),
        ("endswith", "abcdef", "def", True),
        ("endswith", "abcdef", "deg", False),
        ("startswith", "", "", True),
        ("endswith", "", "", True),
        ("startswith", "x", "", True),
    ],
)
def test_startswith_endswith(core: CoreBuiltinAdapter, target, hay, needle, expected):
    assert core.call(target, [hay, needle], {}) is expected


@pytest.mark.parametrize(
    "target,arg,expected",
    [
        ("str", 99, "99"),
        ("int", "42", 42),
        ("float", "3.14", 3.14),
        ("bool", "true", True),
        ("bool", True, True),
    ],
)
def test_type_coercion_success(core: CoreBuiltinAdapter, target, arg, expected):
    assert core.call(target, [arg], {}) == expected


def test_int_invalid_string_raises_value_error(core: CoreBuiltinAdapter):
    with pytest.raises(ValueError):
        core.call("int", ["not_a_number"], {})


def test_float_invalid_string_raises_value_error(core: CoreBuiltinAdapter):
    with pytest.raises(ValueError):
        core.call("float", ["nope"], {})


@pytest.mark.parametrize(
    "arg,expected",
    [
        (0, False),
        ("", False),
        ("false", True),
        ("0", True),
    ],
    ids=["numeric_zero", "empty_string", "str_false_word_truthy", "str_digit_truthy"],
)
def test_bool_coercion_documented(core: CoreBuiltinAdapter, arg, expected):
    # ``core.bool`` delegates to Python ``bool()``: only empty string is falsy;
    # the spellings ``"false"`` / ``"0"`` are non-empty strings and therefore True.
    assert core.call("bool", [arg], {}) is expected


@pytest.mark.parametrize(
    "target,expected",
    [
        ("keys", ["a", "b"]),
        ("values", [1, 2]),
    ],
)
def test_keys_values_populated_dict(core: CoreBuiltinAdapter, target, expected):
    d = {"a": 1, "b": 2}
    assert core.call(target, [d], {}) == expected


@pytest.mark.parametrize("target", ["keys", "values"])
def test_keys_values_empty_dict(core: CoreBuiltinAdapter, target: str):
    assert core.call(target, [{}], {}) == []
