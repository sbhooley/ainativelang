"""Validate/runtime gap closure for ``core.*`` verbs.

Three guarantees:

1. Every ``core.*`` verb listed in the strict contract (``ADAPTER_EFFECT``) and
   not in ``CORE_RUNTIME_UNIMPLEMENTED`` is actually dispatched by
   ``CoreBuiltinAdapter`` (never raises "unsupported core builtin target").
2. Every verb in ``CORE_RUNTIME_UNIMPLEMENTED`` does raise that error, so the
   exclusion list cannot silently go stale in either direction.
3. ``--strict`` compilation rejects programs that call an unimplemented verb
   (``core.MAP`` / ``core.FILTER`` / ``core.REDUCE``).
"""
from __future__ import annotations

import pytest

from compiler_v2 import AICodeCompiler
from runtime.adapters.builtins import CoreBuiltinAdapter
from tooling.effect_analysis import (
    ADAPTER_EFFECT,
    CORE_RUNTIME_UNIMPLEMENTED,
    strict_core_runtime_implemented,
)

pytestmark = pytest.mark.usefixtures("offline_llm_provider_config")

UNSUPPORTED_MSG = "unsupported core builtin target"


@pytest.fixture
def core():
    return CoreBuiltinAdapter()


def _contract_core_verbs() -> list[str]:
    return sorted(k for k in ADAPTER_EFFECT if k.startswith("core."))


def _dispatches(core_adapter: CoreBuiltinAdapter, verb: str) -> bool:
    """True when the runtime recognizes the verb (any error except the unsupported sentinel)."""
    # Try a few arg shapes; implemented verbs may raise IndexError/ValueError on
    # bad arity, but only unrecognized verbs reach the unsupported sentinel.
    for args in ([], [1, 2, 3], [{"a": 1}, "a"], ["x"]):
        try:
            core_adapter.call(verb, args, {})
            return True
        except RuntimeError as exc:
            if UNSUPPORTED_MSG in str(exc):
                return False
            return True
        except Exception:
            continue
    # Every attempt raised a non-sentinel error: the verb is dispatched.
    return True


def test_every_contract_core_verb_is_implemented_or_excluded(core: CoreBuiltinAdapter):
    """Contract/runtime parity: no core verb may validate strict but throw at runtime."""
    gaps = []
    for key in _contract_core_verbs():
        verb = key.split(".", 1)[1].lower()
        implemented = _dispatches(core, verb)
        excluded = key in CORE_RUNTIME_UNIMPLEMENTED
        if not implemented and not excluded:
            gaps.append(f"{key}: in strict contract, not in runtime, not in CORE_RUNTIME_UNIMPLEMENTED")
        if implemented and excluded:
            gaps.append(f"{key}: implemented at runtime but still listed in CORE_RUNTIME_UNIMPLEMENTED")
    assert not gaps, "\n".join(gaps)


@pytest.mark.parametrize("key", sorted(CORE_RUNTIME_UNIMPLEMENTED))
def test_unimplemented_verbs_raise_sentinel(core: CoreBuiltinAdapter, key: str):
    verb = key.split(".", 1)[1].lower()
    with pytest.raises(RuntimeError, match=UNSUPPORTED_MSG):
        core.call(verb, [], {})


@pytest.mark.parametrize(
    "key,expected",
    [
        ("core.MAP", False),
        ("core.map", False),
        ("CORE.MAP", False),
        ("core.FILTER", False),
        ("core.REDUCE", False),
        ("core.ADD", True),
        ("core.TYPE", True),
        ("core.ZIP", True),
        ("http.GET", True),  # non-core keys are out of scope for this check
        ("", True),
    ],
)
def test_strict_core_runtime_implemented_normalizes_case(key: str, expected: bool):
    assert strict_core_runtime_implemented(key) is expected


@pytest.mark.parametrize("verb", ["MAP", "FILTER", "REDUCE"])
def test_strict_compile_rejects_unimplemented_core_verbs(verb: str):
    source = f"S app core noop\n\nL1:\n  R core.{verb} items ->out\n  J out\n"
    compiler = AICodeCompiler(strict_mode=True)
    ir = compiler.compile(source)
    errors = ir.get("errors") or []
    assert any("not implemented at runtime" in str(e) for e in errors), errors


def test_non_strict_compile_warns_on_inline_dict_literal_r_line():
    """Non-strict compiles must at least warn about the inline-dict runtime hazard."""
    source = 'S app core noop\n\nL1:\n  R http.POST "https://x.com/a" {"key": "val"} ->resp\n  J resp\n'
    compiler = AICodeCompiler(strict_mode=False)
    ir = compiler.compile(source)
    assert ir.get("errors") == [], ir.get("errors")
    warnings = [w for w in (ir.get("warnings") or []) if "inline JSON/object literal" in str(w)]
    assert warnings, ir.get("warnings")


def test_strict_compile_accepts_implemented_core_verbs():
    source = 'S app core noop\n\nL1:\n  R core.RANGE 5 ->out\n  J out\n'
    compiler = AICodeCompiler(strict_mode=True)
    ir = compiler.compile(source)
    assert ir.get("errors") == [], ir.get("errors")


# --- New builtin verb behavior -------------------------------------------------

@pytest.mark.parametrize(
    "args,expected",
    [
        ([None], "null"),
        ([True], "bool"),
        ([3], "int"),
        ([3.5], "float"),
        (["s"], "string"),
        ([[1]], "list"),
        ([{"a": 1}], "dict"),
    ],
)
def test_type_verb(core: CoreBuiltinAdapter, args, expected):
    assert core.call("type", args, {}) == expected


def test_format_verb(core: CoreBuiltinAdapter):
    assert core.call("format", ["{0} + {1}", "a", "b"], {}) == "a + b"
    assert core.call("format", ["{} and {}", 1, 2], {}) == "1 and 2"
    assert core.call("format", [], {}) == ""


@pytest.mark.parametrize(
    "args,expected",
    [
        ([3], [0, 1, 2]),
        ([1, 4], [1, 2, 3]),
        ([0, 10, 3], [0, 3, 6, 9]),
        ([], []),
    ],
)
def test_range_verb(core: CoreBuiltinAdapter, args, expected):
    assert core.call("range", args, {}) == expected


def test_pick_and_omit_verbs(core: CoreBuiltinAdapter):
    src = {"a": 1, "b": 2, "c": 3}
    assert core.call("pick", [src, "a", "c"], {}) == {"a": 1, "c": 3}
    assert core.call("pick", [src, ["b"]], {}) == {"b": 2}
    assert core.call("omit", [src, "b"], {}) == {"a": 1, "c": 3}
    assert core.call("omit", [src, ["a", "c"]], {}) == {"b": 2}
    assert core.call("pick", ["not-a-dict", "a"], {}) == {}


def test_zip_verb(core: CoreBuiltinAdapter):
    assert core.call("zip", [[1, 2, 3], ["a", "b"]], {}) == [[1, "a"], [2, "b"]]
    assert core.call("zip", [[1], [2], [3]], {}) == [[1, 2, 3]]
    assert core.call("zip", [], {}) == []


def test_slice_verb(core: CoreBuiltinAdapter):
    assert core.call("slice", [[1, 2, 3, 4], 1, 3], {}) == [2, 3]
    assert core.call("slice", [[1, 2, 3, 4], 2], {}) == [3, 4]
    assert core.call("slice", ["hello", 1, 3], {}) == "el"
