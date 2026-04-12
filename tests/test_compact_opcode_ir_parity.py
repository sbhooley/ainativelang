"""
Compact syntax vs canonical opcode source: compile-time IR parity.

Each row pairs a compact program with the opcode source produced by
``ainl_preprocess.preprocess`` (the contract the compiler consumes after its
internal preprocess pass). Golden opcode strings are kept in sync with the
preprocessor. IR equality is asserted via ``graph_semantic_checksum`` (labels +
graph semantics), which ignores benign ``source``/``cst`` line-ending drift
between the two source forms.
"""
from __future__ import annotations

import difflib
import json
import os
import sys
from textwrap import dedent
from typing import Any, Dict

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ainl_preprocess import preprocess
from compiler_v2 import AICodeCompiler
from tooling.ir_canonical import _semantic_view, graph_semantic_checksum

pytestmark = pytest.mark.usefixtures("offline_llm_provider_config")


def _semantic_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    return _semantic_view(ir or {})


def _ir_diff(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    sa = json.dumps(a, sort_keys=True, indent=2, default=str)
    sb = json.dumps(b, sort_keys=True, indent=2, default=str)
    return "\n".join(
        difflib.unified_diff(
            sa.splitlines(),
            sb.splitlines(),
            fromfile="compact_ir",
            tofile="opcode_ir",
            lineterm="",
        )
    )


_PARITY_CASES = [
    pytest.param(
        "adapter_call_out",
        dedent(
            """
            fetcher:
              resp = http.GET "https://example.com"
              out resp
            """
        ).strip(),
        dedent(
            """
            S app core noop

            L_entry:
              R http.GET "https://example.com" ->resp
              Set _out resp
              J _out


            """
        ).strip(),
        id="adapter_call_out",
    ),
    pytest.param(
        "inputs",
        dedent(
            """
            greet:
              in: name greeting
              out name
            """
        ).strip(),
        dedent(
            """
            S app core noop

            L_entry:
              Set name $name
              Set greeting $greeting
              Set _out name
              J _out


            """
        ).strip(),
        id="inputs",
    ),
    pytest.param(
        "if_branching",
        dedent(
            r"""
            checker:
              if x == "yes":
                out "matched"
              out "nope"
            """
        ).strip(),
        dedent(
            """
            S app core noop

            L_entry:
              Set _cmp_c_cmp_3 (core.eq x "yes")
              If _cmp_c_cmp_3 ->L_c_then_1 ->L_c_cont_2

            L_c_then_1:
              Set _out "matched"
              J _out

            L_c_cont_2:
              Set _out "nope"
              J _out


            """
        ).strip(),
        id="if_branching",
    ),
    pytest.param(
        "out_literal",
        dedent(
            """
            tiny:
              out 42
            """
        ).strip(),
        dedent(
            """
            S app core noop

            L_entry:
              Set _out 42
              J _out


            """
        ).strip(),
        id="out_literal",
    ),
    pytest.param(
        "cron",
        dedent(
            '''
            job @cron "*/5 * * * *":
              t = core.now
              out t
            '''
        ).strip(),
        dedent(
            """
            S core cron "*/5 * * * *"

            L_entry:
              R core.now ->t
              Set _out t
              J _out


            """
        ).strip(),
        id="cron",
    ),
    pytest.param(
        "bare_adapter_call",
        dedent(
            """
            writer:
              core.ADD 1 2
              out done
            """
        ).strip(),
        dedent(
            """
            S app core noop

            L_entry:
              R core.ADD 1 2 ->_
              Set _out done
              J _out


            """
        ).strip(),
        id="bare_adapter_call",
    ),
]


@pytest.mark.parametrize("construct_id,compact_src,opcode_src", _PARITY_CASES)
def test_compact_preprocess_matches_golden_opcode(construct_id, compact_src, opcode_src):
    got = preprocess(compact_src).strip()
    assert got == opcode_src, (
        f"[{construct_id}] preprocess(compact) drifted from golden opcode.\n"
        f"--- expected ---\n{opcode_src}\n--- got ---\n{got}"
    )


@pytest.mark.parametrize("construct_id,compact_src,opcode_src", _PARITY_CASES)
def test_compact_and_opcode_semantic_ir_parity(construct_id, compact_src, opcode_src):
    c = AICodeCompiler()
    ir_compact = c.compile(compact_src)
    ir_opcode = c.compile(opcode_src)
    assert not ir_compact.get("errors"), ir_compact.get("errors")
    assert not ir_opcode.get("errors"), ir_opcode.get("errors")
    h1 = graph_semantic_checksum(ir_compact)
    h2 = graph_semantic_checksum(ir_opcode)
    if h1 != h2:
        pytest.fail(
            f"[{construct_id}] semantic IR checksum mismatch ({h1} vs {h2}).\n"
            + _ir_diff(_semantic_ir(ir_compact), _semantic_ir(ir_opcode))
        )


def test_while_opcode_compiles():
    """Compact syntax does not lower ``While``; still assert opcode graphs compile."""
    c = AICodeCompiler()
    code = dedent(
        """
        S app core noop

        L_entry:
          X i 0
          While (core.lt i 2) ->L_inc ->L_done
        L_inc:
          Set i (core.add i 1)
          While (core.lt i 2) ->L_inc ->L_done
        L_done:
          Set _out i
          J _out
        """
    ).strip()
    ir = c.compile(code + "\n")
    assert not ir.get("errors"), ir.get("errors")
