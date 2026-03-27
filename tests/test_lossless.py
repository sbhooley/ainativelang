"""
Lossless compiler tests: source exact storage, CST, meta with raw_line/tokens, emit_source_exact.
Run: pytest tests/test_lossless.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def test_round_trip_source_exact():
    """compile() output.source.text equals input exactly; emit_source_exact(ir) returns same."""
    c = AICodeCompiler()
    code = "S core web /api\nE /us G ->L1\nL1: J data"
    ir = c.compile(code)
    assert ir.get("source", {}).get("text") == code
    assert ir["source"]["lines"] == code.split("\n")
    assert len(ir["cst"]["lines"]) == 3
    assert c.emit_source_exact(ir) == code


def test_round_trip_preserves_blank_and_comment_lines():
    """Source and CST include blank lines and comment-only lines."""
    c = AICodeCompiler()
    code = "S core web /api\n\n# comment\nL1: J data"
    ir = c.compile(code)
    assert ir["source"]["text"] == code
    assert len(ir["cst"]["lines"]) == 4
    lines = ir["cst"]["lines"]
    assert lines[0]["op_value"] == "S"
    assert lines[1]["op_value"] == "" and not lines[1]["slot_values"]
    assert any(t.get("kind") == "comment" for t in lines[2]["tokens"])
    assert lines[3]["op_value"] == "L1:"
    assert "value" in lines[0]["tokens"][0]


def test_hash_inside_quotes_not_comment():
    """# inside double-quoted string is not treated as comment."""
    c = AICodeCompiler()
    code = 'Desc /us "Hello # not a comment"\n'
    ir = c.compile(code)
    assert ir["source"]["text"] == code
    line0 = ir["cst"]["lines"][0]
    content_tokens = [t for t in line0["tokens"] if t["kind"] in ("bare", "string")]
    assert len(content_tokens) >= 2
    string_vals = [t["raw"] for t in line0["tokens"] if t["kind"] == "string"]
    assert any("# not a comment" in v or "Hello" in v for v in string_vals)
    assert ir["desc"]["endpoints"]["/us"] == "Hello # not a comment"


def test_unterminated_string_line_col():
    """Unterminated string raises ValueError with line and column in message."""
    c = AICodeCompiler()
    code = 'X "unclosed\n'
    with pytest.raises(ValueError) as exc_info:
        c.compile(code)
    msg = str(exc_info.value)
    assert "Unterminated" in msg
    assert "line" in msg.lower() and "column" in msg.lower()
    assert "column 2" in msg  # input is: X "unclosed  (quote starts at col 2)


def test_string_decode_only_quote_and_backslash_escapes():
    """AINL 1.0: common escapes are decoded in strings."""
    c = AICodeCompiler()
    code = r'Desc /x "a\n\tb \" q \\ end"'
    ir = c.compile(code)
    # Desc strips quotes from the slot value. Expected decoded result:
    # - \\n and \\t decode to newline and tab
    # - \\\" becomes "
    # - \\\\ becomes \
    assert ir["desc"]["endpoints"]["/x"] == 'a\n\tb " q \\ end'


def test_unknown_op_meta_has_raw_line_and_tokens():
    """Unknown op is preserved in meta with raw_line and tokens (kind, raw, span)."""
    c = AICodeCompiler()
    code = "S core web /api\nZoo unknown op here\n"
    ir = c.compile(code)
    assert len(ir["meta"]) >= 1
    m = next(x for x in ir["meta"] if x.get("op_value") == "Zoo")
    assert m["raw_line"] == "Zoo unknown op here"
    assert "tokens" in m
    assert "slot_values" in m and isinstance(m["slot_values"], list)
    assert m["slot_values"] == ["unknown", "op", "here"]
    assert "slots_values" in m and m["slots_values"] == m["slot_values"]
    assert any(t.get("kind") == "bare" and t.get("raw") == "Zoo" for t in m["tokens"])
    assert all("span" in t and "line" in t["span"] for t in m["tokens"])


def test_span_indexing_is_line_1_based_col_0_based():
    """Token span indexing is explicit: line starts at 1, columns start at 0."""
    c = AICodeCompiler()
    ir = c.compile("S core web /api")
    line0 = ir["cst"]["lines"][0]
    first = line0["tokens"][0]
    assert first["raw"] == "S"
    assert first["span"]["line"] == 1
    assert first["span"]["col_start"] == 0
    assert first["span"]["col_end"] == 1


def test_ir_semantics_unchanged_minimal_sample():
    """IR services/types/labels unchanged for a minimal existing sample."""
    c = AICodeCompiler()
    code = "S core web /api\nE /us G ->L1\nL1: J data"
    ir = c.compile(code)
    assert "core" in ir["services"]
    assert ir["services"]["core"].get("eps", {}).get("/us", {}).get("G", {}).get("label_id") == "1"
    assert "1" in ir["labels"]
    steps = ir["labels"]["1"]["legacy"]["steps"]
    assert any(s.get("op") == "J" and s.get("var") == "data" for s in steps)
    assert ir["source"]["text"] == code
    assert len(ir["cst"]["lines"]) == 3
    assert c.emit_source_exact(ir) == code
    assert ir["stats"]["ops"] == 3


def test_inline_retry_consumes_backoff():
    c = AICodeCompiler()
    ir = c.compile("L1: Retry 3 1000 J out")
    steps = ir["labels"]["1"]["legacy"]["steps"]
    assert steps[0]["op"] == "Retry"
    assert steps[0]["count"] == "3"
    assert steps[0]["backoff_ms"] == "1000"
    assert steps[1]["op"] == "J"


def test_openapi_array_inner_type_ref_for_model():
    c = AICodeCompiler()
    code = "S core web /api\nD User id:I name:S\nD Wrap users:A[User]\nE /users G ->L1\nL1: J users"
    ir = c.compile(code)
    doc = c.emit_openapi(ir)
    assert '"users"' in doc
    assert '"$ref": "#/components/schemas/User"' in doc


def test_openapi_json_type_maps_to_object_schema():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nD Event payload:J\nE /e G ->L1\nL1: J payload")
    doc = c.emit_openapi(ir)
    assert '"payload"' in doc
    assert '"type": "object"' in doc
    assert '"additionalProperties": true' in doc


def test_openapi_response_data_allows_array_or_object():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nD User id:I\nE /u G ->L1 A[User]\nL1: J users")
    doc = c.emit_openapi(ir)
    assert '"oneOf"' in doc
    assert '"$ref": "#/components/schemas/User"' in doc
