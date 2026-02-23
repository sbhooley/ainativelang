"""
Sanity tests for correctness fixes (E multi-method, quoted strings, Bind, strict, tokenizer).
Run: pytest tests/test_sanity_fixes.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def test_quoted_strings_and_comments():
    """#7/#8: Quoted strings preserved; # only outside quotes."""
    c = AICodeCompiler()
    code = '''
Desc /us "Hello # not a comment"
# comment
'''
    ir = c.compile(code)
    assert ir.get("errors") == []
    assert "/us" in ir.get("desc", {}).get("endpoints", {})
    # Tokenizer preserves quotes; Desc may strip for value.
    text = ir["desc"]["endpoints"]["/us"]
    assert "Hello" in text and "# not a comment" in text


def test_two_methods_same_path():
    """#1: GET and POST on same path both stored."""
    c = AICodeCompiler()
    code = '''
S core web /api
E /us G ->L1
E /us P ->L2
L1: J data
L2: J data
'''
    ir = c.compile(code)
    eps = ir["services"].get("core", {}).get("eps", {})
    assert "/us" in eps
    by_method = eps["/us"]
    assert isinstance(by_method, dict)
    assert "G" in by_method and "P" in by_method
    assert by_method["G"]["label_id"] == "1"
    assert by_method["P"]["label_id"] == "2"


def test_if_targets():
    """If cond ->L2 ->L3 parses then/else label ids."""
    c = AICodeCompiler()
    code = '''
L1: If cond ->L2 ->L3
L2: J ok
L3: J err
'''
    ir = c.compile(code)
    steps = ir["labels"].get("1", {}).get("legacy", {}).get("steps", [])
    assert len(steps) >= 1
    if_step = next(s for s in steps if s.get("op") == "If")
    assert if_step["then"] == "2" and if_step["else"] == "3"
    edges = ir["labels"]["1"].get("edges", [])
    label_edges = [e for e in edges if e.get("to_kind") == "label"]
    assert any(e.get("port") == "then" and e.get("to") == "2" for e in label_edges)
    assert any(e.get("port") == "else" and e.get("to") == "3" for e in label_edges)


def test_endpoint_return_var_strict():
    """Strict: E return_var must match J var."""
    c = AICodeCompiler(strict_mode=True)
    code = '''
S core web /api
E /us G ->L1 ->users
L1: J users
'''
    ir = c.compile(code)
    assert not ir.get("errors"), ir.get("errors")


def test_endpoint_return_var_mismatch_strict():
    """Strict: E return_var mismatch J adds error."""
    c = AICodeCompiler(strict_mode=True)
    code = '''
S core web /api
E /us G ->L1 ->products
L1: J users
'''
    ir = c.compile(code)
    assert any("return_var" in e and "match" in e for e in ir.get("errors", []))


def test_endpoint_arity_invalid_goes_to_meta_and_strict_error():
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile("S core web /api\nE /x G\n")
    assert any(m.get("op_value") == "E" and m.get("reason") == "arity" for m in ir.get("meta", []))
    assert any("op 'E' requires at least 3 slots" in e for e in ir.get("errors", []))


def test_tokenizer_unterminated():
    """Unterminated string raises ValueError with line and column."""
    c = AICodeCompiler()
    code = '''
Desc /x "oops
'''
    with pytest.raises(ValueError) as exc_info:
        c.compile(code)
    msg = str(exc_info.value)
    assert "Unterminated" in msg
    assert "line" in msg.lower() and "column" in msg.lower()


def test_bind_populates_fe_bindings():
    """Bind Db /us ->us stores fe.bindings. U/Bind must be before any Lx: (not inside label block)."""
    c = AICodeCompiler()
    code = '''
S core web /api
E /us G ->L1
U Db
Bind Db /us ->us
L1: J us
'''
    ir = c.compile(code)
    bindings = ir["services"].get("fe", {}).get("bindings", {})
    assert "Db" in bindings
    assert any(b.get("path") == "/us" and b.get("var") == "us" for b in bindings["Db"])


def test_bind_arrow_label_not_treated_as_var():
    """Bind ... ->L<n> must not be treated as state var target."""
    c = AICodeCompiler()
    code = '''
U Db
Bind Db /us P ->L1
'''
    ir = c.compile(code)
    b = ir["services"]["fe"]["bindings"]["Db"][0]
    assert b["method"] == "G"
    assert b["var"] == "data"


def test_react_browser_bind_var_gets_state_and_setter():
    """emit_react_browser must define useState for Bind vars before calling setters."""
    c = AICodeCompiler()
    code = '''
S core web /api
E /us G ->L1
U Db
Bind Db /us G ->users
L1: J users
'''
    ir = c.compile(code)
    react = c.emit_react_browser(ir)
    assert "const [users, setUsers] = useState(" in react
    assert "setUsers(" in react


def test_E_description_recognized_without_quotes_in_slot_values():
    c = AICodeCompiler()
    ir = c.compile('S core web /api\nE /x G ->L1 A[User] My endpoint\nL1: J data\n')
    ep = ir["services"]["core"]["eps"]["/x"]["G"]
    assert ep["return_type"] == "A[User]"
    assert ep["description"] == "My"


def test_label_autoclose_when_top_level_after_label():
    c = AICodeCompiler()
    ir = c.compile("L1: J a\nD User id:I\n")
    assert "User" in ir["types"]


def test_label_autoclose_strict_reports_error():
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile("L1: J a\nD User id:I\n")
    assert any("auto-closed label" in e for e in ir.get("errors", []))


def test_label_autoclose_non_strict_no_error():
    c = AICodeCompiler(strict_mode=False)
    ir = c.compile("L1: J a\nD User id:I\n")
    assert "User" in ir["types"]
    assert not any("auto-closed label" in e for e in ir.get("errors", []))


def test_err_edge_targets_handler_label():
    c = AICodeCompiler()
    ir = c.compile("L1: R db.F User * ->u Err ->L9 J u\nL9: J err\n")
    edges = ir["labels"]["1"].get("edges", [])
    assert any(e.get("to_kind") == "label" and e.get("to") == "9" for e in edges)


def test_react_default_state_by_type():
    """emit_react uses default value by type (not always [])."""
    c = AICodeCompiler()
    code = '''
U Foo
T count:I
T name:S
'''
    ir = c.compile(code)
    react = c.emit_react(ir)
    assert "AINL emitted React/TSX" in react
    assert "React.FC" in react
    assert "(0)" in react
    assert '("")' in react or "(\"\")" in react


def test_react_browser_no_bind_does_not_fetch_all_endpoints():
    c = AICodeCompiler()
    code = '''
S core web /api
E /a G ->L1
E /b G ->L2
L1: J a
L2: J b
U Db
'''
    ir = c.compile(code)
    react = c.emit_react_browser(ir)
    assert "fetch('/api/a'" not in react
    assert "fetch('/api/b'" not in react


def test_react_browser_no_bind_single_endpoint_fallback_fetches():
    c = AICodeCompiler()
    code = '''
S core web /api
E /a G ->L1
L1: J a
U Db
'''
    ir = c.compile(code)
    react = c.emit_react_browser(ir)
    assert "fetch('/api/a'" in react


def test_cst_stores_op_canonical_alias_normalized():
    c = AICodeCompiler()
    ir = c.compile("Env API_KEY required")
    assert ir["cst"]["lines"][0]["op_canonical"] == "ops.Env"


def test_strict_targeted_label_requires_steps_and_single_terminal_j():
    c = AICodeCompiler(strict_mode=True)
    code = "S core web /api\nE /x G ->L1\nL1: Call L2 J out\nL2:\n"
    ir = c.compile(code)
    errs = ir.get("errors", [])
    assert any("Targeted label '2' has no legacy.steps" in e for e in errs)
