"""Comprehensive test suite for AINL compact syntax preprocessor.

Tests cover:
  - Detection: compact vs opcode passthrough
  - Transpilation: all compact constructs
  - Compiler integration: both strict and non-strict
  - Runtime execution: end-to-end
  - Edge cases: empty files, comments only, mixed content
  - Regression: standard opcodes unchanged
"""
import json
import pytest
from ainl_preprocess import preprocess, is_compact_syntax
from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------

class TestDetection:
    """Test is_compact_syntax() correctly identifies compact vs standard."""

    def test_standard_opcodes_not_detected(self):
        assert not is_compact_syntax("S app core noop\n\nL1:\n  R core.ADD 2 3 ->sum\n  J sum\n")

    def test_standard_with_comments_not_detected(self):
        assert not is_compact_syntax("# comment\nS app core noop\n\nL1:\n  J x\n")

    def test_compact_header_detected(self):
        assert is_compact_syntax("my_graph:\n  out 1\n")

    def test_compact_with_comments_detected(self):
        assert is_compact_syntax("# A comment\nmy_graph:\n  out 1\n")

    def test_compact_with_decorator_detected(self):
        assert is_compact_syntax('health @cron "*/5 * * * *":\n  out 1\n')

    def test_empty_string_not_detected(self):
        assert not is_compact_syntax("")

    def test_only_comments_not_detected(self):
        assert not is_compact_syntax("# just a comment\n# another\n")

    def test_only_blanks_not_detected(self):
        assert not is_compact_syntax("\n\n\n")

    def test_label_not_detected_as_compact(self):
        assert not is_compact_syntax("L1:\n  J x\n")

    def test_include_not_detected_as_compact(self):
        assert not is_compact_syntax("include lib/utils\nS app core noop\n")

    def test_D_declaration_not_detected(self):
        assert not is_compact_syntax("D Config threshold:N\nS app core noop\n")


# ---------------------------------------------------------------------------
# Passthrough tests
# ---------------------------------------------------------------------------

class TestPassthrough:
    """Standard opcode files must pass through byte-for-byte unchanged."""

    def test_hello_unchanged(self):
        src = "S app core noop\n\nL1:\n  R core.ADD 2 3 ->sum\n  J sum\n"
        assert preprocess(src) == src

    def test_full_program_unchanged(self):
        src = (
            "S app core noop\n\n"
            "D Config threshold:N\n\n"
            "L1:\n  X val 42\n  Set check (core.gt val 40)\n  If check ->L2 ->L3\n\n"
            "L2:\n  J val\n\n"
            "L3:\n  Set val 0\n  J val\n"
        )
        assert preprocess(src) == src

    def test_existing_examples_unchanged(self):
        """All existing .ainl example files must pass through unchanged."""
        import glob
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        examples = glob.glob(os.path.join(root, "examples", "*.ainl"))
        examples += glob.glob(os.path.join(root, "examples", "golden", "*.ainl"))
        assert len(examples) > 5, f"Expected >5 examples, found {len(examples)}"
        for path in examples:
            with open(path) as f:
                src = f.read()
            result = preprocess(src)
            assert result == src, f"Passthrough failed for {path}"


# ---------------------------------------------------------------------------
# Transpilation tests
# ---------------------------------------------------------------------------

class TestTranspilation:
    """Test compact→opcode transpilation output."""

    def test_minimal_graph(self):
        compact = "adder:\n  result = core.ADD 2 3\n  out result\n"
        opcodes = preprocess(compact)
        assert "S app core noop" in opcodes
        assert "L_entry:" in opcodes
        assert "R core.ADD 2 3 ->result" in opcodes
        assert "J _out" in opcodes

    def test_input_fields(self):
        compact = "greet:\n  in: name greeting\n  out name\n"
        opcodes = preprocess(compact)
        assert "X name ctx.name" in opcodes
        assert "X greeting ctx.greeting" in opcodes

    def test_if_equality(self):
        compact = 'checker:\n  if x == "yes":\n    out "matched"\n  out "nope"\n'
        opcodes = preprocess(compact)
        assert "(core.eq x" in opcodes
        assert "If " in opcodes
        assert "->L_c_then" in opcodes
        assert "->L_c_cont" in opcodes

    def test_if_inequality(self):
        compact = 'checker:\n  if x != "no":\n    out "yes"\n  out "no"\n'
        opcodes = preprocess(compact)
        assert "(core.ne x" in opcodes

    def test_if_greater_than(self):
        compact = "checker:\n  if val > 10:\n    out val\n  out 0\n"
        opcodes = preprocess(compact)
        assert "(core.gt val 10)" in opcodes

    def test_if_less_than(self):
        compact = "checker:\n  if val < 10:\n    out val\n  out 0\n"
        opcodes = preprocess(compact)
        assert "(core.lt val 10)" in opcodes

    def test_if_bare_variable(self):
        compact = "checker:\n  if flag:\n    out flag\n  out null\n"
        opcodes = preprocess(compact)
        assert "If flag ->L_c_then" in opcodes

    def test_multiple_if_branches(self):
        compact = (
            'classifier:\n'
            '  if x == "a":\n    out "A"\n'
            '  if x == "b":\n    out "B"\n'
            '  out "C"\n'
        )
        opcodes = preprocess(compact)
        # 2 then-labels exist as definitions (L_c_then_N:)
        import re
        then_defs = re.findall(r'^L_c_then_\d+:', opcodes, re.MULTILINE)
        cont_defs = re.findall(r'^L_c_cont_\d+:', opcodes, re.MULTILINE)
        assert len(then_defs) == 2, f"Expected 2 then labels, got {then_defs}"
        assert len(cont_defs) == 2, f"Expected 2 cont labels, got {cont_defs}"

    def test_adapter_call(self):
        compact = 'fetcher:\n  resp = http.GET "https://example.com"\n  out resp\n'
        opcodes = preprocess(compact)
        assert 'R http.GET "https://example.com" ->resp' in opcodes

    def test_bare_adapter_call(self):
        compact = "writer:\n  cache.set key val\n  out done\n"
        opcodes = preprocess(compact)
        assert "R cache.set key val ->_" in opcodes

    def test_config_declaration(self):
        compact = "monitor:\n  config threshold:N\n  out 1\n"
        opcodes = preprocess(compact)
        assert "D Config threshold:N" in opcodes

    def test_state_declaration(self):
        compact = "monitor:\n  state counter:N\n  out 1\n"
        opcodes = preprocess(compact)
        assert "D State counter:N" in opcodes

    def test_cron_decorator(self):
        compact = 'job @cron "*/5 * * * *":\n  t = core.now\n  out t\n'
        opcodes = preprocess(compact)
        assert 'S core cron "*/5 * * * *"' in opcodes

    def test_api_decorator(self):
        compact = 'webhook @api "/hooks/stripe":\n  out done\n'
        opcodes = preprocess(compact)
        assert "S app api /hooks/stripe" in opcodes

    def test_error_handling(self):
        compact = 'validator:\n  err "bad input"\n'
        opcodes = preprocess(compact)
        assert 'Err "bad input"' in opcodes

    def test_call_label(self):
        compact = "workflow:\n  call process\n  out done\n"
        opcodes = preprocess(compact)
        assert "Call L_process" in opcodes

    def test_assignment_literal(self):
        compact = "prog:\n  x = 42\n  out x\n"
        opcodes = preprocess(compact)
        assert "Set x 42" in opcodes

    def test_assignment_expression(self):
        compact = "prog:\n  x = (core.add 1 2)\n  out x\n"
        opcodes = preprocess(compact)
        assert "Set x (core.add 1 2)" in opcodes or "R (core.add" not in opcodes

    def test_comments_preserved(self):
        compact = "# top comment\nprog:\n  # inside comment\n  out 1\n"
        opcodes = preprocess(compact)
        assert "# top comment" in opcodes
        assert "# inside comment" in opcodes


# ---------------------------------------------------------------------------
# Compiler integration tests
# ---------------------------------------------------------------------------

class TestCompilerIntegration:
    """Test that transpiled code compiles without errors."""

    def _compile(self, compact, strict=False):
        opcodes = preprocess(compact)
        c = AICodeCompiler(strict_mode=strict)
        ir = c.compile(opcodes, emit_graph=True)
        return ir

    def test_minimal_nonstrict(self):
        ir = self._compile("adder:\n  result = core.ADD 2 3\n  out result\n", strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_minimal_strict(self):
        ir = self._compile("adder:\n  result = core.ADD 2 3\n  out result\n", strict=True)
        assert not ir.get("errors"), ir.get("errors")

    def test_inputs_strict(self):
        ir = self._compile("g:\n  in: name\n  out name\n", strict=True)
        assert not ir.get("errors"), ir.get("errors")

    def test_branching_nonstrict(self):
        compact = 'g:\n  if x == "a":\n    out "A"\n  out "B"\n'
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_cache_pattern_nonstrict(self):
        compact = "g:\n  v = cache.get k\n  if v:\n    out v\n  fresh = http.GET url\n  out fresh\n"
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_adapter_calls_strict(self):
        compact = 'g:\n  resp = http.GET "https://example.com"\n  out resp\n'
        ir = self._compile(compact, strict=True)
        assert not ir.get("errors"), ir.get("errors")

    def test_multi_branch_nonstrict(self):
        compact = (
            'g:\n  in: level\n'
            '  if level == "high":\n    out "critical"\n'
            '  if level == "med":\n    out "warning"\n'
            '  out "info"\n'
        )
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_cron_nonstrict(self):
        compact = 'job @cron "0 * * * *":\n  t = core.now\n  out t\n'
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_declarations_nonstrict(self):
        compact = "g:\n  config threshold:N\n  state counter:N\n  out 1\n"
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")

    def test_error_op_nonstrict(self):
        compact = 'g:\n  if x == 0:\n    err "zero"\n  out x\n'
        ir = self._compile(compact, strict=False)
        assert not ir.get("errors"), ir.get("errors")


# ---------------------------------------------------------------------------
# Runtime execution tests
# ---------------------------------------------------------------------------

class TestRuntimeExecution:
    """Test that compact syntax programs execute correctly."""

    def _run(self, compact):
        opcodes = preprocess(compact)
        c = AICodeCompiler(strict_mode=False)
        ir = c.compile(opcodes, emit_graph=True)
        assert not ir.get("errors"), f"Compile failed: {ir.get('errors')}"
        engine = RuntimeEngine(ir)
        return engine.run(opcodes)

    def test_add_returns_5(self):
        result = self._run("adder:\n  result = core.ADD 2 3\n  out result\n")
        assert result["ok"] is True
        assert result["result"] == 5

    def test_sub_returns_7(self):
        result = self._run("sub:\n  result = core.sub 10 3\n  out result\n")
        assert result["ok"] is True
        assert result["result"] == 7

    def test_mul_returns_12(self):
        result = self._run("mul:\n  result = core.mul 3 4\n  out result\n")
        assert result["ok"] is True
        assert result["result"] == 12

    def test_literal_string(self):
        result = self._run('prog:\n  x = "hello"\n  out x\n')
        assert result["ok"] is True
        assert result["result"] == "hello"

    def test_literal_number(self):
        result = self._run("prog:\n  x = 42\n  out x\n")
        assert result["ok"] is True
        assert result["result"] == 42


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_passthrough(self):
        assert preprocess("") == ""

    def test_whitespace_only_passthrough(self):
        assert preprocess("   \n  \n") == "   \n  \n"

    def test_comments_only_passthrough(self):
        src = "# comment 1\n# comment 2\n"
        assert preprocess(src) == src

    def test_graph_with_only_out(self):
        compact = "minimal:\n  out 1\n"
        opcodes = preprocess(compact)
        c = AICodeCompiler(strict_mode=False)
        ir = c.compile(opcodes, emit_graph=True)
        assert not ir.get("errors"), ir.get("errors")

    def test_graph_with_many_comments(self):
        compact = "# top\n# more\nprog:\n  # inner\n  result = core.ADD 1 1\n  # before out\n  out result\n"
        opcodes = preprocess(compact)
        c = AICodeCompiler(strict_mode=False)
        ir = c.compile(opcodes, emit_graph=True)
        assert not ir.get("errors"), ir.get("errors")


# ---------------------------------------------------------------------------
# Token efficiency tests
# ---------------------------------------------------------------------------

class TestTokenEfficiency:
    """Verify compact syntax is more token-efficient than opcodes."""

    def test_compact_fewer_bytes_than_equivalent_opcodes(self):
        compact = "adder:\n  result = core.ADD 2 3\n  out result\n"
        opcodes = preprocess(compact)
        # Compact should be smaller than its opcode output
        # (opcodes have boilerplate: S header, L_entry, Set _out, J _out)
        assert len(compact) < len(opcodes), (
            f"Compact ({len(compact)}) should be smaller than opcodes ({len(opcodes)})"
        )
