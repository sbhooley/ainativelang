"""
AINL Compact Syntax Preprocessor.

Transpiles the human-friendly compact syntax into standard AINL opcodes
that the compiler (compiler_v2.py) already understands. This is a pure
string transformation — no AST, no IR, no compiler dependency.

Compact syntax detection: if the first non-comment, non-blank line matches
`<name>:` and is NOT a valid opcode line (S, D, L<n>:, include, etc.),
treat the file as compact syntax.

Standard .ainl opcode files pass through UNCHANGED — zero impact on
existing programs.

Design constraints:
  - Output must compile in both strict and non-strict mode.
  - Comparisons use: Set <var> (core.<op> a b) then If <var> ->L1 ->L2
  - All labels use L_<name> format (underscore prefix).
  - No invented opcodes — only S, D, L, R, X, Set, If, J, Call, Err.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Detection: is this compact syntax or standard opcodes?
# ---------------------------------------------------------------------------

# Standard opcode first-tokens that mean "this is already opcode format"
_OPCODE_PREFIXES = frozenset([
    "S", "D", "E", "R", "J", "U", "T", "Q", "X",
    "If", "Set", "Filt", "Sort", "Loop", "While",
    "CacheGet", "CacheSet", "QueuePut", "Tx", "Enf",
    "Inc", "Call", "Err", "Retry",
    "Role", "Allow", "Aud", "Adm", "Ver", "Compat",
    "Tst", "Mock", "Desc", "Rel", "Idx", "API", "Dep",
    "SLA", "Run", "Svc", "Contract",
    "include",
])

_LABEL_RE = re.compile(r'^L\w+:')


def is_compact_syntax(source: str) -> bool:
    """Return True if source uses compact syntax (not standard opcodes)."""
    for line in source.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # If it starts with a known opcode or label, it's standard
        first_token = stripped.split()[0] if stripped.split() else ""
        if first_token in _OPCODE_PREFIXES:
            return False
        if _LABEL_RE.match(stripped):
            return False
        # If it looks like "name:" or "name @decorator "...":" at the start
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*(?:@\w+\s+"[^"]*"\s*)?:\s*$', stripped):
            return True
        # Anything else — not compact, not standard, bail out safe
        return False
    return False


# ---------------------------------------------------------------------------
# Compact syntax parser
# ---------------------------------------------------------------------------

class _CompactLine:
    """Parsed representation of one compact-syntax line."""
    __slots__ = ("indent", "raw", "kind", "data", "lineno")

    def __init__(self, indent: int, raw: str, kind: str, data: dict, lineno: int):
        self.indent = indent
        self.raw = raw
        self.kind = kind  # header, in, config, state, assign, if, out, call, err, comment, blank, adapter_call
        self.data = data
        self.lineno = lineno


def _parse_indent(line: str) -> Tuple[int, str]:
    """Return (indent_level, stripped_content)."""
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    return indent, stripped


def _classify_line(line: str, lineno: int, is_first_content: bool) -> _CompactLine:
    """Classify a single compact-syntax line."""
    indent, stripped = _parse_indent(line)

    if not stripped:
        return _CompactLine(indent, line, "blank", {}, lineno)

    if stripped.startswith("#"):
        return _CompactLine(indent, line, "comment", {"text": stripped}, lineno)

    # Graph header: name:  or  name @cron "...":
    if is_first_content and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*(?:@\w+\s+"[^"]*"\s*)?:\s*$', stripped):
        m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:@(\w+)\s+"([^"]*)"\s*)?:\s*$', stripped)
        if m:
            return _CompactLine(indent, line, "header", {
                "name": m.group(1),
                "decorator": m.group(2),  # e.g. "cron"
                "decorator_arg": m.group(3),  # e.g. "*/5 * * * *"
            }, lineno)

    # Input declaration: in: field1 field2 ...
    if stripped.startswith("in:"):
        fields = stripped[3:].strip().split()
        return _CompactLine(indent, line, "in", {"fields": fields}, lineno)

    # Config declaration: config name:type
    if stripped.startswith("config "):
        rest = stripped[7:].strip()
        return _CompactLine(indent, line, "config", {"decl": rest}, lineno)

    # State declaration: state name:type
    if stripped.startswith("state "):
        rest = stripped[6:].strip()
        return _CompactLine(indent, line, "state", {"decl": rest}, lineno)

    # Output: out <expr>
    if stripped.startswith("out "):
        expr = stripped[4:].strip()
        return _CompactLine(indent, line, "out", {"expr": expr}, lineno)
    if stripped == "out":
        return _CompactLine(indent, line, "out", {"expr": "done"}, lineno)

    # Error: err "message"
    if stripped.startswith("err "):
        msg = stripped[4:].strip()
        return _CompactLine(indent, line, "err", {"msg": msg}, lineno)

    # Call: call <label>
    if stripped.startswith("call "):
        target = stripped[5:].strip()
        return _CompactLine(indent, line, "call", {"target": target}, lineno)

    # If statement: if <cond>:
    if stripped.startswith("if ") and stripped.rstrip().endswith(":"):
        cond = stripped[3:].rstrip().rstrip(":")
        return _CompactLine(indent, line, "if", {"cond": cond.strip()}, lineno)

    # Assignment: var = adapter.op args...  OR  var = literal  OR  var = (expr)
    m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', stripped)
    if m:
        var = m.group(1)
        rhs = m.group(2).strip()
        # Check if RHS is an adapter call: first token contains a dot
        # and does NOT start with ( which indicates an expression
        first_tok = rhs.split()[0] if rhs.split() else ""
        if "." in first_tok and not first_tok.startswith("("):
            parts = rhs.split(None, 1)
            adapter_op = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            return _CompactLine(indent, line, "adapter_call", {
                "var": var, "adapter_op": adapter_op, "args": args
            }, lineno)
        else:
            return _CompactLine(indent, line, "assign", {
                "var": var, "expr": rhs
            }, lineno)

    # Bare adapter call without assignment: adapter.op args
    if "." in stripped.split()[0] if stripped.split() else False:
        parts = stripped.split(None, 1)
        adapter_op = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return _CompactLine(indent, line, "adapter_call", {
            "var": "_", "adapter_op": adapter_op, "args": args
        }, lineno)

    # Fallback: treat as raw opcode passthrough
    return _CompactLine(indent, line, "passthrough", {"raw": stripped}, lineno)


# ---------------------------------------------------------------------------
# Transpiler: compact lines → opcode lines
# ---------------------------------------------------------------------------

class _Transpiler:
    """Converts parsed compact lines into AINL opcode source."""

    def __init__(self):
        self._label_counter = 0
        self._output: List[str] = []
        self._graph_name = ""
        self._if_stack: List[dict] = []  # tracks nested if blocks

    def _next_label(self, hint: str = "") -> str:
        self._label_counter += 1
        if hint:
            return f"_c_{hint}_{self._label_counter}"
        return f"_c_{self._label_counter}"

    def transpile(self, lines: List[_CompactLine]) -> str:
        """Convert compact lines to opcode source."""
        # First pass: collect structure
        header = None
        body_lines: List[_CompactLine] = []
        for cl in lines:
            if cl.kind == "header":
                header = cl
            elif cl.kind in ("blank", "comment"):
                body_lines.append(cl)
            else:
                body_lines.append(cl)

        if header is None:
            # No header found — passthrough
            return "\n".join(cl.raw for cl in lines)

        # Emit S header
        self._graph_name = header.data["name"]
        decorator = header.data.get("decorator")
        decorator_arg = header.data.get("decorator_arg")

        if decorator == "cron" and decorator_arg:
            self._output.append(f'S core cron "{decorator_arg}"')
        elif decorator == "api" and decorator_arg:
            self._output.append(f'S app api {decorator_arg}')
        else:
            self._output.append("S app core noop")
        self._output.append("")

        # Emit declarations and body
        self._emit_body(body_lines)

        return "\n".join(self._output) + "\n"

    def _emit_body(self, lines: List[_CompactLine]):
        """Process body lines and emit opcodes."""
        # Separate declarations from executable lines
        decls: List[_CompactLine] = []
        exec_lines: List[_CompactLine] = []
        for cl in lines:
            if cl.kind in ("config", "state"):
                decls.append(cl)
            else:
                exec_lines.append(cl)

        # Emit declarations
        for cl in decls:
            if cl.kind == "config":
                self._output.append(f'D Config {cl.data["decl"]}')
            elif cl.kind == "state":
                self._output.append(f'D State {cl.data["decl"]}')

        if decls:
            self._output.append("")

        # Process executable lines into a flat sequence of labeled blocks
        # We need to handle if/else blocks by creating labels
        self._emit_block(exec_lines, "L_entry")

    def _emit_block(self, lines: List[_CompactLine], entry_label: str):
        """Emit a block of lines starting at entry_label."""
        current_label = entry_label
        self._output.append(f"{current_label}:")

        # Input declarations become R core.GET ctx "field" ->field
        i = 0
        while i < len(lines):
            cl = lines[i]

            if cl.kind == "blank":
                i += 1
                continue

            if cl.kind == "comment":
                self._output.append(f"  {cl.data['text']}")
                i += 1
                continue

            if cl.kind == "in":
                for field in cl.data["fields"]:
                    # Use X ctx.<field> pattern — works in both strict and non-strict
                    self._output.append(f"  X {field} ctx.{field}")
                i += 1
                continue

            if cl.kind == "adapter_call":
                var = cl.data["var"]
                adapter_op = cl.data["adapter_op"]
                args = cl.data["args"]
                if args:
                    self._output.append(f"  R {adapter_op} {args} ->{var}")
                else:
                    self._output.append(f"  R {adapter_op} ->{var}")
                i += 1
                continue

            if cl.kind == "assign":
                var = cl.data["var"]
                expr = cl.data["expr"]
                # Use Set for all assignments — safe in both strict and non-strict,
                # avoids X runtime quirks with unknown function names
                self._output.append(f"  Set {var} {expr}")
                i += 1
                continue

            if cl.kind == "out":
                expr = cl.data["expr"]
                self._output.append(f"  Set _out {expr}")
                self._output.append("  J _out")
                i += 1
                continue

            if cl.kind == "err":
                msg = cl.data["msg"]
                self._output.append(f"  Err {msg}")
                i += 1
                continue

            if cl.kind == "call":
                target = cl.data["target"]
                self._output.append(f"  Call L_{target}")
                i += 1
                continue

            if cl.kind == "if":
                # Collect the if-body (indented lines after the if)
                cond = cl.data["cond"]
                if_indent = cl.indent
                if_body: List[_CompactLine] = []
                j = i + 1
                while j < len(lines) and lines[j].kind in ("blank", "comment"):
                    j += 1
                while j < len(lines):
                    if lines[j].kind == "blank":
                        if_body.append(lines[j])
                        j += 1
                        continue
                    if lines[j].indent > if_indent:
                        if_body.append(lines[j])
                        j += 1
                    else:
                        break

                # Generate labels for then/else branches
                then_label = self._next_label("then")
                cont_label = self._next_label("cont")

                # Parse condition: var == "value", var != "value", or just var
                cond_var = self._emit_condition(cond)

                self._output.append(f"  If {cond_var} ->L{then_label} ->L{cont_label}")
                self._output.append("")

                # Emit then-block
                self._output.append(f"L{then_label}:")
                self._emit_if_body(if_body)
                # If the then-body doesn't end with out/J, jump to continuation
                if not self._last_emitted_is_terminal():
                    self._output.append(f"  J _out")
                self._output.append("")

                # Continuation label — rest of the block continues here
                current_label = f"L{cont_label}"
                self._output.append(f"{current_label}:")

                i = j
                continue

            if cl.kind == "passthrough":
                self._output.append(f"  {cl.data['raw']}")
                i += 1
                continue

            # Unknown — passthrough
            self._output.append(f"  # [preprocessor: unhandled] {cl.raw.strip()}")
            i += 1

        # If block doesn't end with J, add a default
        if not self._last_emitted_is_terminal():
            self._output.append("  Set _out null")
            self._output.append("  J _out")

    def _emit_condition(self, cond: str) -> str:
        """Parse a condition and emit comparison ops. Return the var to branch on."""
        cond = cond.strip()

        # Pattern: var == "value" or var == value
        m = re.match(r'^(\S+)\s*==\s*(.+)$', cond)
        if m:
            left = m.group(1)
            right = m.group(2).strip()
            cmp_var = self._next_label("cmp")
            self._output.append(f"  Set _cmp{cmp_var} (core.eq {left} {right})")
            return f"_cmp{cmp_var}"

        # Pattern: var != "value"
        m = re.match(r'^(\S+)\s*!=\s*(.+)$', cond)
        if m:
            left = m.group(1)
            right = m.group(2).strip()
            cmp_var = self._next_label("cmp")
            self._output.append(f"  Set _cmp{cmp_var} (core.ne {left} {right})")
            return f"_cmp{cmp_var}"

        # Pattern: var > value
        m = re.match(r'^(\S+)\s*>\s*(.+)$', cond)
        if m:
            left = m.group(1)
            right = m.group(2).strip()
            cmp_var = self._next_label("cmp")
            self._output.append(f"  Set _cmp{cmp_var} (core.gt {left} {right})")
            return f"_cmp{cmp_var}"

        # Pattern: var < value
        m = re.match(r'^(\S+)\s*<\s*(.+)$', cond)
        if m:
            left = m.group(1)
            right = m.group(2).strip()
            cmp_var = self._next_label("cmp")
            self._output.append(f"  Set _cmp{cmp_var} (core.lt {left} {right})")
            return f"_cmp{cmp_var}"

        # Pattern: var >= value
        m = re.match(r'^(\S+)\s*>=\s*(.+)$', cond)
        if m:
            left = m.group(1)
            right = m.group(2).strip()
            cmp_var = self._next_label("cmp")
            self._output.append(f"  Set _cmp{cmp_var} (core.gte {left} {right})")
            return f"_cmp{cmp_var}"

        # Bare variable — use directly
        return cond

    def _emit_if_body(self, lines: List[_CompactLine]):
        """Emit the body of an if block (already at correct label)."""
        for cl in lines:
            if cl.kind == "blank":
                continue
            if cl.kind == "comment":
                self._output.append(f"  {cl.data['text']}")
            elif cl.kind == "adapter_call":
                var = cl.data["var"]
                adapter_op = cl.data["adapter_op"]
                args = cl.data["args"]
                if args:
                    self._output.append(f"  R {adapter_op} {args} ->{var}")
                else:
                    self._output.append(f"  R {adapter_op} ->{var}")
            elif cl.kind == "assign":
                var = cl.data["var"]
                expr = cl.data["expr"]
                self._output.append(f"  Set {var} {expr}")
            elif cl.kind == "out":
                expr = cl.data["expr"]
                self._output.append(f"  Set _out {expr}")
                self._output.append("  J _out")
            elif cl.kind == "err":
                self._output.append(f"  Err {cl.data['msg']}")
            elif cl.kind == "call":
                self._output.append(f"  Call L_{cl.data['target']}")
            elif cl.kind == "passthrough":
                self._output.append(f"  {cl.data['raw']}")

    def _last_emitted_is_terminal(self) -> bool:
        """Check if the last non-blank emitted line is a J or Err."""
        for line in reversed(self._output):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("J ") or stripped.startswith("Err "):
                return True
            return False
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess(source: str) -> str:
    """Transpile compact AINL syntax to opcodes. Standard opcodes pass through unchanged.

    This function is the ONLY public API. It is safe to call on any .ainl source —
    standard opcode files return unchanged, compact syntax files get transpiled.
    """
    if not is_compact_syntax(source):
        return source

    # Parse lines
    lines = source.split("\n")
    parsed: List[_CompactLine] = []
    is_first_content = True
    for lineno, line in enumerate(lines, 1):
        cl = _classify_line(line, lineno, is_first_content)
        parsed.append(cl)
        if cl.kind not in ("blank", "comment"):
            is_first_content = False

    # Transpile
    t = _Transpiler()
    return t.transpile(parsed)
