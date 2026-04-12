"""MCP ``ainl_compile`` / ``ainl_run`` contract tests for ``frame_hints``.

Invokes the real :func:`scripts.ainl_mcp_server.ainl_compile` and
:func:`scripts.ainl_mcp_server.ainl_run` (no mocks), following the import and
call style of ``tests/test_mcp_server.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Core-only graphs — no LLM / network (offline-safe).
_CODE_WITH_ANNOTATIONS = """# frame: user_id: string
# frame: score: int
S app core noop
L1:
R core.ADD score 1 ->bumped
R core.CONCAT user_id "-" ->tag
R core.CONCAT tag bumped ->out
J out
"""

_CODE_NO_ANNOTATIONS = """S app core noop
L1:
R core.ADD 2 3 ->sum
J sum
"""

_CODE_MULTI_ANNOTATIONS = """# frame: alpha: string
# frame: beta: string
# frame: gamma: string
S app core noop
L1:
R core.CONCAT alpha beta ->ab
R core.CONCAT ab gamma ->out
J out
"""

_CODE_WHITESPACE_ANNOTATION = """#  frame:  myVar :  string
S app core noop
L1:
R core.CONCAT myVar "!" ->out
J out
"""

_CODE_CUSTOM_TYPE = """# frame: id: uuid
S app core noop
L1:
R core.CONCAT "id:" id ->out
J out
"""

_CODE_MALFORMED_FRAME_COMMENT = """# frame: onlyone
S app core noop
L1:
R core.ADD 1 2 ->x
J x
"""

_CODE_ROUNDTRIP = """# frame: seed: int
S app core noop
L1:
R core.ADD seed 1 ->out
J out
"""


@pytest.fixture(autouse=True)
def _clear_ainl_config(monkeypatch: pytest.MonkeyPatch):
    """Ensure MCP path does not try to register LLM adapters (offline)."""
    monkeypatch.delenv("AINL_CONFIG", raising=False)


def _hint_names(hints: list) -> list[str]:
    return [h["name"] for h in hints]


def test_frame_hints_nonempty_with_annotations():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_WITH_ANNOTATIONS, strict=True)
    assert r["ok"] is True
    hints = r.get("frame_hints")
    assert isinstance(hints, list)
    assert len(hints) >= 2
    for h in hints:
        assert "name" in h and "type" in h
        if "description" in h:
            assert isinstance(h["description"], str)
    names = _hint_names(hints)
    assert "user_id" in names and "score" in names


def test_frame_hints_empty_without_annotations():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_NO_ANNOTATIONS, strict=True)
    assert r["ok"] is True
    assert "frame_hints" in r
    assert r["frame_hints"] == []


def test_frame_hints_multiple_declaration_order():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_MULTI_ANNOTATIONS, strict=True)
    assert r["ok"] is True
    hints = r["frame_hints"]
    comment_hints = [h for h in hints if h.get("source") == "comment"]
    assert [h["name"] for h in comment_hints] == ["alpha", "beta", "gamma"]


def test_frame_hints_whitespace_in_comment():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_WHITESPACE_ANNOTATION, strict=True)
    assert r["ok"] is True
    h = next(x for x in r["frame_hints"] if x["name"] == "myVar")
    assert h["type"] == "string"


def test_frame_hints_custom_type_string():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_CUSTOM_TYPE, strict=True)
    assert r["ok"] is True
    h = next(x for x in r["frame_hints"] if x["name"] == "id")
    assert h["type"] == "uuid"


def test_frame_hints_malformed_comment_no_crash():
    from scripts.ainl_mcp_server import ainl_compile

    r = ainl_compile(_CODE_MALFORMED_FRAME_COMMENT, strict=True)
    assert r["ok"] is True
    hints = r["frame_hints"]
    only = next(x for x in hints if x["name"] == "onlyone")
    assert only["type"] == "any"


def test_compile_run_roundtrip_frame_from_hints():
    from scripts.ainl_mcp_server import ainl_compile, ainl_run

    comp = ainl_compile(_CODE_ROUNDTRIP, strict=True)
    assert comp["ok"] is True
    frame = {}
    for h in comp["frame_hints"]:
        if h["name"] == "seed":
            frame["seed"] = 41
    run = ainl_run(_CODE_ROUNDTRIP, strict=True, frame=frame)
    assert run["ok"] is True
    assert run["out"] == 42
