"""
AINL 1.0 — Ultra-compact compiler.
Syntax: 1-char OP + slots (space-delimited; quoted strings preserved). Parses to IR for React/TS/Python/MT5/Scraper emission.
Spec: docs/AINL_SPEC.md. Canonical IR: labels[id].nodes/edges + legacy.steps.
Lossless: source stored exactly; tokenizer emits Token(kind, raw, value, span); meta keeps raw_line + token spans.
"""
import json
import re
from typing import Dict, Any, List, Optional, Tuple

# --- Lossless token model: kind in ("bare","string","ws","comment"), span = {line, col_start, col_end}
# line is 1-based; columns are 0-based [col_start, col_end). ---
def _make_token(kind: str, raw: str, value: str, line: int, col_start: int, col_end: int) -> Dict[str, Any]:
    return {"kind": kind, "raw": raw, "value": value, "span": {"line": line, "col_start": col_start, "col_end": col_end}}

# --- Type shorthand for Prisma/TS
TYPE_MAP = {
    "I": "Int", "i": "Int", "S": "String", "s": "String",
    "B": "Boolean", "F": "Float", "D": "DateTime", "J": "Json",
}
def normalize_type(t: str) -> str:
    """E.g. E[Ad,Us] -> enum, A[User] -> User[]."""
    t = t.strip()
    if t.startswith("A[") and t.endswith("]"):
        inner = t[2:-1]
        return f"{normalize_type(inner)}[]"
    if t.startswith("E[") and t.endswith("]"):
        return "String"  # enum as string in Prisma or dedicated enum
    return TYPE_MAP.get(t, t)


def default_value_for_type(typ: str) -> str:
    """JS/TS default initial value for normalized type (fix #2: not always [])."""
    t = (typ or "any").strip()
    if "[]" in t:
        return "[]"
    if t in ("String", "string", "S", "s"):
        return '""'
    if t in ("Int", "Float", "number", "I", "i", "F"):
        return "0"
    if t in ("Boolean", "boolean", "B"):
        return "false"
    if t in ("DateTime", "D", "J", "Json"):
        return "null"
    return "null"


# Unprefixed module ops → canonical module.op (spec: IR must store canonical form).
MODULE_ALIASES = {
    "Env": "ops.Env", "Sec": "ops.Sec", "M": "ops.M", "Tr": "ops.Tr",
    "Deploy": "ops.Deploy", "EnvT": "ops.EnvT", "Flag": "ops.Flag", "Lim": "ops.Lim",
    "Tok": "fe.Tok", "Brk": "fe.Brk", "Sp": "fe.Sp", "Comp": "fe.Comp",
    "Copy": "fe.Copy", "Theme": "fe.Theme", "i18n": "fe.i18n", "A11y": "fe.A11y",
    "Off": "fe.Off", "Help": "fe.Help", "Wiz": "fe.Wiz", "FRetry": "fe.FetchRetry",
    "RagSrc": "rag.Src", "RagChunk": "rag.Chunk", "RagEmbed": "rag.Embed",
    "RagStore": "rag.Store", "RagIdx": "rag.Idx", "RagRet": "rag.Ret",
    "RagAug": "rag.Aug", "RagGen": "rag.Gen", "RagPipe": "rag.Pipe",
}
KNOWN_MODULES = {"ops", "fe", "rag", "arch", "test", "core"}

# Canonical op registry: scope and minimum slot arity.
# scope:
# - "top": declaration/top-level op
# - "label": label-step op
# - "any": allowed both top-level and inside labels
OP_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Core declarations
    "S": {"scope": "top", "min_slots": 2},
    "D": {"scope": "top", "min_slots": 1},
    "E": {"scope": "top", "min_slots": 3},
    "L:": {"scope": "top", "min_slots": 0},  # pseudo-key for label declarations like L1:
    "U": {"scope": "top", "min_slots": 0},
    "T": {"scope": "top", "min_slots": 1},
    "Q": {"scope": "top", "min_slots": 1},
    "Sc": {"scope": "top", "min_slots": 2},
    "Cr": {"scope": "top", "min_slots": 2},
    "P": {"scope": "top", "min_slots": 3},
    "C": {"scope": "top", "min_slots": 3},
    "Rt": {"scope": "top", "min_slots": 2},
    "Bind": {"scope": "top", "min_slots": 3},
    "Lay": {"scope": "top", "min_slots": 2},
    "Fm": {"scope": "top", "min_slots": 2},
    "Tbl": {"scope": "top", "min_slots": 2},
    "Ev": {"scope": "top", "min_slots": 3},
    "A": {"scope": "top", "min_slots": 2},
    "Inc": {"scope": "top", "min_slots": 1},
    # Governance/metadata declarations
    "Role": {"scope": "top", "min_slots": 1},
    "Allow": {"scope": "top", "min_slots": 2},
    "Aud": {"scope": "top", "min_slots": 2},
    "Adm": {"scope": "top", "min_slots": 1},
    "Ver": {"scope": "top", "min_slots": 1},
    "Compat": {"scope": "top", "min_slots": 1},
    "Tst": {"scope": "top", "min_slots": 1},
    "Mock": {"scope": "top", "min_slots": 3},
    "Desc": {"scope": "top", "min_slots": 2},
    "Rel": {"scope": "top", "min_slots": 4},
    "Idx": {"scope": "top", "min_slots": 2},
    "API": {"scope": "top", "min_slots": 1},
    "Dep": {"scope": "top", "min_slots": 2},
    "SLA": {"scope": "top", "min_slots": 3},
    "Run": {"scope": "top", "min_slots": 2},
    "Svc": {"scope": "top", "min_slots": 1},
    "Contract": {"scope": "top", "min_slots": 3},
    # Label/control flow
    "R": {"scope": "any", "min_slots": 0},
    "J": {"scope": "any", "min_slots": 0},
    "If": {"scope": "label", "min_slots": 2},
    "Err": {"scope": "label", "min_slots": 1},
    "Retry": {"scope": "label", "min_slots": 0},
    "Call": {"scope": "label", "min_slots": 1},
    "Set": {"scope": "label", "min_slots": 2},
    "Filt": {"scope": "label", "min_slots": 5},
    "Sort": {"scope": "label", "min_slots": 3},
}


def _iter_eps(eps: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Return [(path, method, ep), ...] for all endpoints. Supports eps[path][method]=ep and legacy eps[path]=ep."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for path, val in eps.items():
        if not isinstance(val, dict):
            continue
        if "label_id" in val or "method" in val:
            out.append((path, val.get("method", "G"), val))
        else:
            for method, ep in val.items():
                if isinstance(ep, dict):
                    out.append((path, method, ep))
    return out


class AICodeCompiler:
    def __init__(self, strict_mode: bool = False, strict_reachability: bool = False) -> None:
        self.strict_mode = strict_mode
        self.strict_reachability = strict_reachability
        self._errors: List[str] = []
        self.services: Dict[str, Dict] = {}
        self.labels: Dict[str, Dict[str, Any]] = {}  # id -> { steps: [...], slots?: [...] }
        self.types: Dict[str, Dict[str, Any]] = {}
        self.crons: List[Dict[str, str]] = []
        self.current_ui: Optional[str] = None
        self.current_label: Optional[str] = None
        self.config = {"env": [], "secrets": []}
        self.observability = {"metrics": [], "trace": False}
        self.deploy: Dict[str, Any] = {"strategy": "rolling", "env_target": "", "flags": []}
        self.limits: Dict[str, Any] = {"per_path": {}, "per_tenant": 0}
        self.roles: List[str] = []
        self.allow: List[Dict[str, Any]] = []
        self.audit: Dict[str, Any] = {}
        self.admin: Dict[str, Any] = {}
        self.desc: Dict[str, Any] = {"endpoints": {}, "types": {}}
        self.runbooks: Dict[str, List[str]] = {}
        self.ver: Optional[str] = None
        self.compat: Optional[str] = None
        self.tests: List[Dict[str, Any]] = []
        self.api_opts: Dict[str, Any] = {"style": "rest", "version_prefix": "", "deprecate": [], "sla": {}}
        self._current_test: Optional[Dict[str, Any]] = None
        self.rag: Dict[str, Any] = {"sources": {}, "chunking": {}, "embeddings": {}, "stores": {}, "indexes": {}, "retrievers": {}, "augment": {}, "generate": {}, "pipelines": {}}
        self.meta: List[Dict[str, Any]] = []  # unknown ops preserved (lossless compiler)

    def tokenize_line(self, line: str) -> List[str]:
        """Legacy/simple tokenizer (string tokens only).

        Notes:
        - Preserves double-quoted string raw text (including quote characters).
        - Treats '#' as comment start only when outside quotes.
        - Does NOT emit token kinds/spans and does NOT provide decoded string values.
        - Prefer tokenize_line_lossless() for compiler/lossless behavior.
        """
        out: List[str] = []
        buf: List[str] = []
        in_q = False
        esc = False
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if not in_q and ch == "#":
                break
            if esc:
                buf.append(ch)
                esc = False
                i += 1
                continue
            if ch == "\\" and in_q:
                esc = True
                i += 1
                continue
            if ch == '"':
                buf.append(ch)
                in_q = not in_q
                i += 1
                continue
            if not in_q and ch in " \t":
                if buf:
                    out.append("".join(buf))
                    buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
        if in_q:
            raise ValueError("Unterminated string literal")
        if buf:
            out.append("".join(buf))
        return out

    def parse_line(self, line: str) -> Tuple[str, List[str]]:
        """Legacy/simple parser based on tokenize_line(); kept for compatibility."""
        parts = self.tokenize_line(line.strip())
        if not parts:
            return "", []
        return parts[0], parts[1:]

    def tokenize_line_lossless(self, line: str, lineno: int) -> List[Dict[str, Any]]:
        """Emit Token dicts (kind, raw, value, span) including ws and comment.
        Span uses 1-based line number and 0-based columns.
        String decoding intentionally treats only \\\" and \\\\ as escapes; all other
        backslash sequences are preserved literally to match AINL 1.0.
        Raises ValueError with line+column for unterminated strings.
        """
        out: List[Dict[str, Any]] = []
        i = 0
        n = len(line)
        in_q = False
        esc = False
        col_start = 0
        while i < n:
            ch = line[i]
            if not in_q and ch == "#":
                raw = line[i:]
                out.append(_make_token("comment", raw, raw, lineno, i, n))
                return out
            if not in_q and ch in " \t":
                start = i
                while i < n and line[i] in " \t":
                    i += 1
                raw = line[start:i]
                out.append(_make_token("ws", raw, raw, lineno, start, i))
                continue
            if in_q:
                if esc:
                    esc = False
                    i += 1
                    continue
                if ch == "\\" and i + 1 < n and line[i + 1] in '"\\':
                    # Scanner escape semantics intentionally match decode semantics:
                    # only \" and \\ are escape pairs in AINL 1.0.
                    esc = True
                    i += 1
                    continue
                if ch == '"':
                    i += 1
                    raw = line[col_start:i]
                    value_parts: List[str] = []
                    j = col_start + 1
                    while j < i - 1:
                        if line[j] == "\\" and j + 1 < i - 1 and line[j + 1] in '"\\':
                            value_parts.append(line[j + 1])
                            j += 2
                        else:
                            value_parts.append(line[j])
                            j += 1
                    value = "".join(value_parts)
                    out.append(_make_token("string", raw, value, lineno, col_start, i))
                    in_q = False
                    col_start = i
                else:
                    i += 1
                continue
            if ch == '"':
                col_start = i
                in_q = True
                i += 1
                continue
            start = i
            while i < n and line[i] not in " \t" and line[i] != "#" and line[i] != '"':
                i += 1
            raw = line[start:i]
            out.append(_make_token("bare", raw, raw, lineno, start, i))
        if in_q:
            raise ValueError(f"Unterminated string literal at line {lineno}, column {col_start}")
        return out

    def parse_line_lossless(self, tokens: List[Dict[str, Any]], raw_line: str, lineno: Optional[int] = None) -> Dict[str, Any]:
        """Build LineNode: original_line, op_value/slot_values + full token payload (kind, raw, value, span)."""
        content = [t for t in tokens if t["kind"] in ("bare", "string")]
        op_value = content[0]["value"] if content else ""
        slot_values = [t["value"] for t in content[1:]] if len(content) > 1 else []
        token_ser = [{"kind": t["kind"], "raw": t["raw"], "value": t["value"], "span": t["span"]} for t in tokens]
        line_no = lineno if lineno is not None else (tokens[0]["span"]["line"] if tokens else 1)
        return {
            "lineno": line_no,
            "original_line": raw_line,
            "op_value": op_value,
            "op_canonical": "",
            "slot_values": slot_values,
            "tokens": token_ser,
        }

    def _meta_record(self, lineno: int, line_node: Dict[str, Any], reason: Optional[str] = None) -> Dict[str, Any]:
        """Create a stable lossless meta record shape for unknown/rejected lines."""
        slot_values = list(line_node.get("slot_values", []))
        rec = {
            "lineno": lineno,
            "op_value": line_node.get("op_value", ""),
            "slot_values": slot_values,
            # Backward-compat alias for older consumers.
            "slots_values": slot_values,
            "raw_line": line_node.get("original_line", ""),
            "tokens": list(line_node.get("tokens", [])),
        }
        if reason:
            rec["reason"] = reason
        return rec

    # Step ops allowed inside a label block (spec: only these execute in core).
    STEP_OPS = frozenset({"R", "J", "If", "Err", "Retry", "Call", "Set", "Filt", "Sort"})

    def _ensure_label(self, lid: str) -> None:
        if lid not in self.labels:
            self.labels[lid] = {"nodes": [], "edges": [], "legacy": {"steps": []}}
        elif "legacy" not in self.labels[lid]:
            old_steps = self.labels[lid].pop("steps", [])
            self.labels[lid].setdefault("nodes", [])
            self.labels[lid].setdefault("edges", [])
            self.labels[lid]["legacy"] = {"steps": old_steps}

    def _label_steps(self, lid: str) -> List[Dict[str, Any]]:
        """Return the legacy.steps list for label (spec: steps live under legacy.steps)."""
        self._ensure_label(lid)
        return self.labels[lid]["legacy"]["steps"]

    @staticmethod
    def _parse_arrow_lbl(tok: str) -> Optional[str]:
        """Parse ->L<n> or L<n> to numeric label id; else None."""
        if not tok:
            return None
        if tok.startswith("->L") and tok[3:].strip().isdigit():
            return tok[3:].strip()
        if tok.startswith("L") and tok[1:].lstrip().split(":")[0].isdigit():
            return tok[1:].lstrip().split(":")[0]
        return None

    @staticmethod
    def _norm_lid(x: Optional[str]) -> Optional[str]:
        """Normalize label id tokens like ->L1, L1, 1, L1: to plain numeric string '1'."""
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        if s.startswith("->L"):
            s = s[3:]
        elif s.startswith("L"):
            s = s[1:]
        if ":" in s:
            s = s.split(":")[-1]
        return s

    def _op_spec(self, op: str) -> Dict[str, Any]:
        """Lookup canonical op spec from OP_REGISTRY with sensible defaults."""
        if op.startswith("L") and op.endswith(":"):
            return OP_REGISTRY["L:"]
        if "." in op:
            # module.op declarations are top-level metadata by design
            return {"scope": "top", "min_slots": 0}
        return OP_REGISTRY.get(op, {"scope": "top", "min_slots": 0})

    def _steps_to_graph(self, lid: str) -> None:
        """Deterministic lowering: legacy.steps -> nodes, edges (canonical n1,n2,...). If/Err/Retry get proper ports."""
        body = self.labels.get(lid)
        if not body:
            return
        leg = body.get("legacy", {})
        steps = leg.get("steps", [])
        if not steps:
            body["nodes"] = body.get("nodes", [])
            body["edges"] = body.get("edges", [])
            body["entry"] = None
            body["exits"] = []
            return
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        last_nid: Optional[str] = None
        k = 0
        for s in steps:
            op = s.get("op")
            if op not in self.STEP_OPS:
                continue
            k += 1
            nid = f"n{k}"
            effect = "io" if op == "R" else ("pure" if op in ("Set", "Filt", "Sort", "If") else "pure")
            if op == "Call":
                effect = "io"
            nodes.append({"id": nid, "op": op, "effect": effect, "data": s})
            if op == "If":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node"})
                then_id = self._norm_lid(s.get("then"))
                else_id = self._norm_lid(s.get("else"))
                if then_id:
                    edges.append({"from": nid, "to": then_id, "port": "then", "to_kind": "label"})
                if else_id:
                    edges.append({"from": nid, "to": else_id, "port": "else", "to_kind": "label"})
                last_nid = None
            elif op == "Err":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "port": "err", "to_kind": "node"})
                handler = self._norm_lid(s.get("handler"))
                if handler:
                    edges.append({"from": nid, "to": handler, "to_kind": "label"})
                last_nid = None
            elif op == "Retry":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "port": "retry", "to_kind": "node"})
                last_nid = nid
            else:
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node"})
                last_nid = nid
        exits = [{"node": n["id"], "var": n["data"].get("var", "data")} for n in nodes if n["op"] == "J"]
        body["nodes"] = nodes
        body["edges"] = edges
        body["entry"] = nodes[0]["id"] if nodes else None
        body["exits"] = exits

    def _steps_to_graph_all(self) -> None:
        """Populate nodes/edges/entry/exits for every label from legacy.steps."""
        for lid in list(self.labels.keys()):
            self._steps_to_graph(lid)

    def _parse_req_slots(self, slots: List[str]) -> Optional[Dict[str, Any]]:
        """Parse R per spec: adapter target (r_arg)* ->out. Single-token arrow; out from last slot."""
        if not slots:
            return None
        parts = list(slots)
        out_var = "res"
        if parts and parts[-1].startswith("->") and not parts[-1].startswith("->L"):
            out_var = parts[-1][2:]
            parts = parts[:-1]
        if len(parts) < 2:
            return {"adapter": "?", "target": "", "args": [], "out": out_var, "raw": slots}
        adapter = parts[0]  # e.g. db.F, api.G
        target = parts[1]
        args = parts[2:]
        # Derived for backward compat (entity, src, req_op, fields). No dot -> src=adapter, req_op="" (fix #5).
        if "." in adapter:
            src, req_op = adapter.split(".", 1)
        else:
            src, req_op = adapter, ""
        entity = target if target and not target.startswith("/") else ""
        fields = args[0] if args else "*"
        return {
            "adapter": adapter,
            "target": target,
            "args": args,
            "out": out_var,
            "src": src,
            "req_op": req_op.upper() if req_op else "",
            "entity": entity,
            "fields": fields,
            "raw": slots,
        }

    def compile(self, code: str, emit_graph: bool = True) -> Dict[str, Any]:
        source_text = code
        lines = code.split("\n")
        source_lines = list(lines)
        cst_lines: List[Dict[str, Any]] = []
        parsed_ops = 0
        self.current_label = None
        self._errors = []
        self.meta = []
        for lineno, line in enumerate(lines, 1):
            try:
                tokens = self.tokenize_line_lossless(line, lineno)
            except ValueError as e:
                self._errors.append(f"Line {lineno}: {e}")
                raise
            line_node = self.parse_line_lossless(tokens, line, lineno)
            cst_lines.append(line_node)
            op_value = line_node["op_value"]
            slots = line_node["slot_values"]
            if not op_value and not slots:
                continue
            parsed_ops += 1
            op = MODULE_ALIASES.get(op_value, op_value)
            line_node["op_canonical"] = op
            mod, mop = None, None
            if "." in op:
                mod, mop = op.split(".", 1)
                if self.strict_mode and mod not in KNOWN_MODULES:
                    self._errors.append(f"Line {lineno}: unknown module {mod!r} in {op!r}")
            spec = self._op_spec(op)
            min_slots = int(spec.get("min_slots", 0))
            if min_slots and len(slots) < min_slots:
                self.meta.append(self._meta_record(lineno, line_node, reason="arity"))
                if self.strict_mode:
                    self._errors.append(
                        f"Line {lineno}: op {op!r} requires at least {min_slots} slots, got {len(slots)}"
                    )
                continue

            # Label body auto-close: if a non-step/non-label op appears, treat it as top-level.
            # This prevents declarations after a label from being trapped as inside_label_block.
            if self.current_label is not None and op not in self.STEP_OPS and not (op.startswith("L") and op.endswith(":")):
                if self.strict_mode:
                    self._errors.append(
                        f"Line {lineno}: auto-closed label L{self.current_label} on top-level op {op!r} inside label block"
                    )
                self.current_label = None
            # Scope validation from canonical op registry (data-driven).
            if self.current_label is None and spec.get("scope") == "label":
                self.meta.append(self._meta_record(lineno, line_node, reason="scope"))
                if self.strict_mode:
                    self._errors.append(f"Line {lineno}: label-only op {op!r} used at top-level")
                continue

            if op == "S":
                if len(slots) >= 2:
                    name, mode = slots[0], slots[1]
                    path = slots[2] if len(slots) > 2 else ""
                    self.services[name] = {"mode": mode, "path": path, "eps": {}, "ui": {}}

            elif op == "D":
                if slots:
                    name = slots[0]
                    fields = {}
                    optional = []
                    required = []
                    for f in slots[1:]:
                        if ":" in f:
                            key, typ = f.split(":", 1)
                            if typ.endswith("?"):
                                fields[key] = typ[:-1]
                                optional.append(key)
                            elif typ.endswith("!"):
                                fields[key] = typ[:-1]
                                required.append(key)
                            else:
                                fields[key] = typ
                    self.types[name] = {"fields": fields}
                    if optional:
                        self.types[name]["optional"] = optional
                    if required:
                        self.types[name]["required"] = required

            elif op == "E":
                # Spec: E path method ->L<n> [->return_var]. label_tok = ->L<n>; optional return_tok = ->id.
                if len(slots) >= 3:
                    path, method = slots[0], slots[1]
                    lbl = slots[2]
                    if not lbl.startswith("->L"):
                        if getattr(self, "strict_mode", False):
                            self._errors.append(f"E: slot 3 must be ->L<number>, got {lbl!r}")
                        label_id = lbl.lstrip("L").split(":")[-1] if lbl else "anon"
                    else:
                        label_id = lbl[3:].lstrip()  # after ->L
                    return_var = None
                    idx = 3
                    if len(slots) > idx and slots[idx].startswith("->") and not slots[idx].startswith("->L"):
                        return_var = slots[idx][2:]
                        idx += 1
                    ep = {"method": method, "label_id": label_id, "return_var": return_var}
                    ep["tgt"] = "->L" + str(label_id)  # backward compat for emitters
                    # Optional endpoint contract after optional return_var: return_type, description.
                    if len(slots) > idx:
                        s_type = slots[idx]
                        if s_type.startswith("A[") or s_type.startswith("E[") or s_type in ("I", "i", "F", "S", "s", "B", "D", "J"):
                            ep["return_type"] = s_type
                            idx += 1
                    if len(slots) > idx:
                        ep["description"] = slots[idx]
                    # Key by (path, method) so GET and POST on same path both exist (fix #1).
                    core = self.services.setdefault("core", {})
                    core.setdefault("mode", "")
                    core.setdefault("path", "")
                    core.setdefault("eps", {})
                    core.setdefault("ui", {})
                    core["eps"].setdefault(path, {})[method.upper()] = ep

            elif op.startswith("L") and op.endswith(":"):
                label = op[1:-1]
                self.current_label = label
                self._ensure_label(label)
                self.labels[label]["slots"] = slots
                leg = self.labels[label]["legacy"]
                # Parse inline steps: R ... J var | If | Set | Filt | Sort | Err | Retry | Call
                i = 0
                step_ops = ("J", "If", "Set", "Filt", "Sort", "Err", "Retry", "Call")
                while i < len(slots):
                    if slots[i] == "R":
                        r_slots = []
                        i += 1
                        while i < len(slots) and slots[i] not in step_ops:
                            r_slots.append(slots[i])
                            i += 1
                        parsed = self._parse_req_slots(r_slots)
                        leg["steps"].append({"op": "R", **(parsed or {"raw": r_slots})})
                    elif slots[i] == "J":
                        var = slots[i + 1] if i + 1 < len(slots) else "data"
                        leg["steps"].append({"op": "J", "var": var})
                        i += 2
                    elif slots[i] == "If" and i + 2 <= len(slots):
                        cond = slots[i + 1]
                        then_id = self._parse_arrow_lbl(slots[i + 2])
                        else_id = self._parse_arrow_lbl(slots[i + 3]) if i + 3 < len(slots) else None
                        if self.strict_mode and then_id is None:
                            self._errors.append(f"Line {lineno}: If then target must be ->L<n> or L<n>, got {slots[i + 2]!r}")
                        leg["steps"].append({"op": "If", "cond": cond, "then": then_id or slots[i + 2].lstrip("L").split(":")[-1], "else": else_id})
                        i += 4 if i + 3 < len(slots) else 3
                    elif slots[i] == "Set" and i + 3 <= len(slots):
                        leg["steps"].append({"op": "Set", "name": slots[i + 1], "ref": slots[i + 2]})
                        i += 3
                    elif slots[i] == "Filt" and i + 6 <= len(slots):
                        leg["steps"].append({"op": "Filt", "name": slots[i + 1], "ref": slots[i + 2], "field": slots[i + 3], "cmp": slots[i + 4], "value": slots[i + 5]})
                        i += 6
                    elif slots[i] == "Sort" and i + 4 <= len(slots):
                        # Sort name ref field [asc|desc]: need 4 tokens min, optional 5th for order (fix #4).
                        order = slots[i + 4] if (i + 4 < len(slots) and slots[i + 4] in ("asc", "desc")) else "asc"
                        leg["steps"].append({"op": "Sort", "name": slots[i + 1], "ref": slots[i + 2], "field": slots[i + 3], "order": order})
                        i += 5 if (i + 4 < len(slots) and slots[i + 4] in ("asc", "desc")) else 4
                    elif slots[i] == "Err" and i + 1 < len(slots):
                        h_id = self._parse_arrow_lbl(slots[i + 1])
                        leg["steps"].append({"op": "Err", "handler": h_id or slots[i + 1].lstrip("L").split(":")[-1]})
                        i += 2
                    elif slots[i] == "Retry":
                        count = slots[i + 1] if i + 1 < len(slots) else "3"
                        backoff = slots[i + 2] if i + 2 < len(slots) else "0"
                        leg["steps"].append({"op": "Retry", "count": count, "backoff_ms": backoff})
                        if i + 2 < len(slots):
                            i += 3
                        elif i + 1 < len(slots):
                            i += 2
                        else:
                            i += 1
                    elif slots[i] == "Call" and i + 1 < len(slots):
                        lid = slots[i + 1].lstrip("L").split(":")[-1]
                        leg["steps"].append({"op": "Call", "label": lid})
                        i += 2
                    else:
                        i += 1

            elif op == "R":
                parsed = self._parse_req_slots(slots)
                if self.current_label:
                    self._label_steps(self.current_label).append({"op": "R", **parsed} if parsed else {"op": "R", "raw": slots})
                else:
                    self._label_steps("_anon").append({"op": "R", **(parsed or {}), "raw": slots})

            elif op == "J":
                var = slots[0] if slots else "data"
                if self.current_label:
                    self._label_steps(self.current_label).append({"op": "J", "var": var})
                else:
                    self._label_steps("_anon").append({"op": "J", "var": var})

            elif op == "U":
                name = slots[0] if slots else "Anon"
                props = slots[1:] if len(slots) > 1 else []
                self.services.setdefault("fe", {}).setdefault("ui", {})[name] = props if isinstance(props, list) else [props]
                self.current_ui = name

            elif op == "T":
                if slots and self.current_ui:
                    first = slots[0]
                    if ":" in first:
                        var, typ = first.split(":", 1)
                    else:
                        var, typ = first, (slots[1] if len(slots) > 1 else "any")
                    # FE IR: states live under fe.states, not fe.ui.states (spec §7).
                    states = self.services.setdefault("fe", {}).setdefault("states", {})
                    states.setdefault(self.current_ui, []).append((var.strip(), typ.strip()))

            elif op == "Q":
                if len(slots) >= 1:
                    name = slots[0]
                    max_sz = slots[1] if len(slots) > 1 else "100"
                    retry = slots[2] if len(slots) > 2 else "3"
                    self.services.setdefault("queue", {}).setdefault("defs", {})[name] = {"maxSize": max_sz, "retry": retry}

            elif op == "Sc":
                if len(slots) >= 2:
                    name, url = slots[0], slots[1]
                    selectors = {}
                    for s in slots[2:]:
                        if "=" in s:
                            sel, fld = s.split("=", 1)
                            selectors[sel] = fld
                    self.services.setdefault("scrape", {}).setdefault("defs", {})[name] = {"url": url, "selectors": selectors}

            elif op == "Cr":
                if len(slots) >= 2:
                    label = slots[0]
                    expr = " ".join(slots[1:])  # e.g. */15 * * * *
                    self.crons.append({"label": label, "expr": expr})

            elif op == "P":
                # P is declaration only (spec: never executable). Payment in labels = R pay.*
                if len(slots) >= 3:
                    name, amt, cur = slots[0], slots[1], slots[2]
                    desc = slots[3] if len(slots) > 3 else ""
                    self.services.setdefault("pay", {}).setdefault("defs", {})[name] = {"amount": amt, "currency": cur, "desc": desc}
                    # Do not add P to label steps; if inside label, non-strict: optional rewrite to R pay.Charge later

            elif op == "C":
                if len(slots) >= 3:
                    name, key, ttl = slots[0], slots[1], slots[2]
                    default = slots[3] if len(slots) > 3 else None
                    self.services.setdefault("cache", {}).setdefault("defs", {})[name] = {"key": key, "ttl": ttl, "default": default}

            elif op == "Rt":
                if len(slots) >= 2:
                    path, ui = slots[0], slots[1]
                    self.services.setdefault("fe", {}).setdefault("routes", []).append({"path": path, "ui": ui})
            elif op == "Bind":
                # Bind ui_name path [method] ->var: UI explicitly binds endpoint to state var (fix #3, #13).
                if len(slots) >= 3:
                    ui_name = slots[0]
                    path = slots[1]
                    is_var = lambda t: isinstance(t, str) and t.startswith("->") and not t.startswith("->L")
                    if len(slots) >= 4 and is_var(slots[3]):
                        method = slots[2].upper()
                        var = slots[3][2:]
                    else:
                        method = "G"
                        var = slots[2][2:] if (len(slots) >= 3 and is_var(slots[2])) else "data"
                    self.services.setdefault("fe", {}).setdefault("bindings", {}).setdefault(ui_name, []).append({"path": path, "method": method, "var": var})

            elif op == "Lay":
                if len(slots) >= 2:
                    name, slot_list = slots[0], slots[1:]
                    self.services.setdefault("fe", {}).setdefault("layouts", {})[name] = {"slots": slot_list}

            elif op == "Fm":
                if len(slots) >= 2:
                    name, typ = slots[0], slots[1]
                    fields = slots[2:] if len(slots) > 2 else []
                    self.services.setdefault("fe", {}).setdefault("forms", {})[name] = {"type": typ, "fields": fields}

            elif op == "Tbl":
                if len(slots) >= 2:
                    name, typ = slots[0], slots[1]
                    columns = slots[2:] if len(slots) > 2 else []
                    self.services.setdefault("fe", {}).setdefault("tables", {})[name] = {"type": typ, "columns": columns}

            elif op == "Ev":
                if len(slots) >= 3:
                    component, event, target = slots[0], slots[1], slots[2]
                    self.services.setdefault("fe", {}).setdefault("events", []).append(
                        {"component": component, "event": event, "target": target}
                    )

            elif op == "A":
                if len(slots) >= 2:
                    kind, arg = slots[0], slots[1]
                    extra = slots[2] if len(slots) > 2 else ""
                    self.services.setdefault("auth", {})["kind"] = kind
                    self.services["auth"]["arg"] = arg
                    if extra:
                        self.services["auth"]["extra"] = extra

            # --- Core: control flow, vars, composition ---
            elif op == "If":
                if len(slots) >= 2 and self.current_label:
                    cond = slots[0]
                    then_l = slots[1][2:] if slots[1].startswith("->") else slots[1]
                    else_l = slots[2][2:] if len(slots) > 2 and slots[2].startswith("->") else (slots[2] if len(slots) > 2 else None)
                    if then_l.startswith("L"):
                        then_l = then_l[1:]
                    if ":" in then_l:
                        then_l = then_l.split(":")[-1]
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "If", "cond": cond, "then": then_l, "else": else_l})
            elif op == "Err":
                if slots and self.current_label:
                    handler = slots[0][2:] if slots[0].startswith("->") else slots[0]
                    if handler.startswith("L"):
                        handler = handler[1:]
                    if ":" in handler:
                        handler = handler.split(":")[-1]
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Err", "handler": handler})
            elif op == "Retry":
                if self.current_label:
                    count = slots[0] if slots else "3"
                    backoff = slots[1] if len(slots) > 1 else "0"
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Retry", "count": count, "backoff_ms": backoff})
            elif op == "Call":
                if slots and self.current_label:
                    lid = slots[0]
                    if lid.startswith("L"):
                        lid = lid[1:]
                    if ":" in lid:
                        lid = lid.split(":")[-1]
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Call", "label": lid})
            elif op == "Set":
                if len(slots) >= 2 and self.current_label:
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Set", "name": slots[0], "ref": slots[1]})
            elif op == "Filt":
                if len(slots) >= 5 and self.current_label:
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Filt", "name": slots[0], "ref": slots[1], "field": slots[2], "cmp": slots[3], "value": slots[4]})
            elif op == "Sort":
                if len(slots) >= 3 and self.current_label:
                    order = slots[3] if len(slots) > 3 else "asc"
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Sort", "name": slots[0], "ref": slots[1], "field": slots[2], "order": order})
            elif op == "Inc":
                if slots:
                    path = slots[0]
                    self.services.setdefault("_includes", []).append(path)

            # --- Module ops (canonical mod.mop after normalization) ---
            elif mod == "ops" and mop == "Env":
                if slots:
                    name = slots[0]
                    kind = slots[1] if len(slots) > 1 else "optional"
                    default = slots[2] if len(slots) > 2 else None
                    self.config["env"].append({"name": name, "required": kind == "required", "default": default})
            elif mod == "ops" and mop == "Sec":
                if len(slots) >= 2:
                    self.config["secrets"].append({"name": slots[0], "ref": slots[1]})
            elif mod == "ops" and mop == "M":
                if len(slots) >= 2:
                    self.observability["metrics"].append({"name": slots[0], "type": slots[1]})
            elif mod == "ops" and mop == "Tr":
                if slots:
                    self.observability["trace"] = slots[0].lower() == "on"
            elif mod == "ops" and mop == "Deploy":
                if slots:
                    self.deploy["strategy"] = slots[0]
            elif mod == "ops" and mop == "EnvT":
                if slots:
                    self.deploy["env_target"] = slots[0]
            elif mod == "ops" and mop == "Flag":
                if slots:
                    name = slots[0]
                    default = "on" if len(slots) < 2 else slots[1]
                    self.deploy.setdefault("flags", []).append({"name": name, "default": default})
            elif mod == "ops" and mop == "Lim":
                if len(slots) >= 2:
                    tgt = slots[0]
                    rpm = slots[1]
                    if tgt == "tenant":
                        self.limits["per_tenant"] = int(rpm) if rpm.isdigit() else 0
                    else:
                        self.limits["per_path"][tgt] = rpm

            # --- RBAC, audit, admin ---
            elif op == "Role":
                if slots:
                    self.roles.append(slots[0])
            elif op == "Allow":
                if len(slots) >= 2:
                    entry = {"role": slots[0]}
                    if len(slots) >= 3 and slots[1].startswith("/"):
                        entry["path"] = slots[1]
                        entry["method"] = (slots[2] if len(slots) > 2 else "G").upper()
                    else:
                        entry["ui"] = slots[1]
                    self.allow.append(entry)
            elif op == "Aud":
                if len(slots) >= 2:
                    self.audit = {"event": slots[0], "retention_days": slots[1]}
            elif op == "Adm":
                if slots:
                    self.admin = {"ui": slots[0], "entities": slots[1:]}

            # --- Versioning ---
            elif op == "Ver":
                if slots:
                    self.ver = slots[0]
            elif op == "Compat":
                if slots:
                    self.compat = slots[0]

            # --- Testing ---
            elif op == "Tst":
                if slots:
                    self._current_test = {"label": slots[0].lstrip("L"), "mocks": []}
                    self.tests.append(self._current_test)
            elif op == "Mock":
                if slots and len(slots) >= 3 and self._current_test is not None:
                    self._current_test["mocks"].append({"adapter": slots[0], "key": slots[1], "value": " ".join(slots[2:])})
                elif slots and len(slots) >= 3:
                    self.tests.append({"label": None, "mocks": [{"adapter": slots[0], "key": slots[1], "value": " ".join(slots[2:])}]})

            # --- Desc (endpoint or type description) ---
            elif op == "Desc":
                if len(slots) >= 2:
                    target = slots[0]
                    text = " ".join(slots[1:]).strip('"\'')
                    if target.startswith("/"):
                        self.desc["endpoints"][target] = text
                    else:
                        self.desc["types"][target] = text

            # --- Data: relations, indexes ---
            elif op == "Rel":
                if len(slots) >= 4:
                    t1, kind, t2 = slots[0], slots[1], slots[2]
                    fk = slots[3] if len(slots) > 3 else None
                    self.types.setdefault(t1, {"fields": {}}).setdefault("relations", []).append({"kind": kind, "target": t2, "fk": fk})
            elif op == "Idx":
                if len(slots) >= 2:
                    typ = slots[0]
                    self.types.setdefault(typ, {"fields": {}}).setdefault("indexes", []).append(slots[1:])

            # --- Arch: API, deprecate, SLA, runbooks, Svc, Contract ---
            elif op == "API":
                if slots:
                    self.api_opts["style"] = slots[0]
                    if len(slots) > 1:
                        self.api_opts["version_prefix"] = slots[1]
            elif op == "Dep":
                if len(slots) >= 2:
                    self.api_opts["deprecate"].append({"path": slots[0], "at": slots[1]})
            elif op == "SLA":
                if len(slots) >= 3:
                    path = slots[0]
                    self.api_opts["sla"][path] = {"p99_ms": slots[1], "availability": slots[2]}
            elif op == "Run":
                if len(slots) >= 2:
                    self.runbooks[slots[0]] = slots[1:]
            elif op == "Svc":
                if slots:
                    self.services.setdefault("_boundaries", {})[slots[0]] = slots[1] if len(slots) > 1 else ""
            elif op == "Contract":
                if len(slots) >= 3:
                    self.services.setdefault("_contracts", []).append({"path": slots[0], "method": slots[1], "response_type": slots[2] if len(slots) > 2 else None})

            # --- fe.* module ---
            elif mod == "fe" and mop == "Tok":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("tokens", {})[slots[0]] = slots[1]
            elif mod == "fe" and mop == "Brk":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("breakpoints", {})[slots[0]] = slots[1]
            elif mod == "fe" and mop == "Sp":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("spacing", {})[slots[0]] = slots[1]
            elif mod == "fe" and mop == "Comp":
                if len(slots) >= 1:
                    self.services.setdefault("fe", {}).setdefault("components", {})[slots[0]] = {"slots": slots[1:]}
            elif mod == "fe" and mop == "Copy":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("copy", {})[slots[0]] = " ".join(slots[1:]).strip('"\'')
            elif mod == "fe" and mop == "Theme":
                if slots:
                    self.services.setdefault("fe", {})["theme"] = slots[0]
            elif mod == "fe" and mop == "i18n":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("i18n", {})[slots[0]] = " ".join(slots[1:]).strip('"\'')
            elif mod == "fe" and mop == "A11y":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("a11y", {})[slots[0]] = slots[1]
            elif mod == "fe" and mop == "Off":
                if slots:
                    path = slots[0]
                    ttl = slots[1] if len(slots) > 1 else "3600"
                    self.services.setdefault("fe", {}).setdefault("offline", []).append({"path": path, "ttl": ttl})
            elif mod == "fe" and mop == "Help":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("help", {})[slots[0]] = slots[1]
            elif mod == "fe" and mop == "Wiz":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {}).setdefault("wizard", {})[slots[0]] = slots[1:]
            elif mod == "fe" and mop == "FetchRetry":
                if len(slots) >= 2:
                    self.services.setdefault("fe", {})["retry"] = {"count": slots[0], "backoff_ms": slots[1]}

            # --- rag.* module ---
            elif mod == "rag" and mop == "Src":
                if len(slots) >= 3:
                    self.rag["sources"][slots[0]] = {"type": slots[1], "path": slots[2]}
            elif mod == "rag" and mop == "Chunk":
                if len(slots) >= 4:
                    self.rag["chunking"][slots[0]] = {"source": slots[1], "strategy": slots[2], "size": slots[3], "overlap": slots[4] if len(slots) > 4 else "0"}
            elif mod == "rag" and mop == "Embed":
                if len(slots) >= 2:
                    self.rag["embeddings"][slots[0]] = {"model": slots[1], "dim": slots[2] if len(slots) > 2 else None}
            elif mod == "rag" and mop == "Store":
                if len(slots) >= 2:
                    self.rag["stores"][slots[0]] = {"type": slots[1]}
            elif mod == "rag" and mop == "Idx":
                if len(slots) >= 5:
                    self.rag["indexes"][slots[0]] = {"source": slots[1], "chunk": slots[2], "embed": slots[3], "store": slots[4]}
            elif mod == "rag" and mop == "Ret":
                if len(slots) >= 3:
                    self.rag["retrievers"][slots[0]] = {"idx": slots[1], "top_k": slots[2], "filter": slots[3] if len(slots) > 3 else None}
            elif mod == "rag" and mop == "Aug":
                if len(slots) >= 5:
                    self.rag["augment"][slots[0]] = {"tpl": slots[1], "chunks_var": slots[2], "query_var": slots[3], "out": slots[4]}
            elif mod == "rag" and mop == "Gen":
                if len(slots) >= 3:
                    self.rag["generate"][slots[0]] = {"model": slots[1], "prompt_var": slots[2], "out": slots[3] if len(slots) > 3 else "out"}
            elif mod == "rag" and mop == "Pipe":
                if len(slots) >= 4:
                    self.rag["pipelines"][slots[0]] = {"ret": slots[1], "aug": slots[2], "gen": slots[3]}

            else:
                # Lossless: preserve unknown ops in meta (spec §5). Module validation already done above.
                self.meta.append(self._meta_record(lineno, line_node))

        if emit_graph:
            self._steps_to_graph_all()

        # Spec: emit only nodes, edges, legacy.steps (no bare "steps"). Runtime reads legacy.steps.

        # Strict-mode checks (spec §3.5, cheap validations).
        if self.strict_mode:
            core = self.services.get("core", {})
            eps = core.get("eps", {})
            targeted_labels: set = set()
            endpoint_labels: set = set()
            for path, method, ep in _iter_eps(eps):
                label_id = self._norm_lid(ep.get("label_id", ""))
                if label_id:
                    targeted_labels.add(label_id)
                    endpoint_labels.add(label_id)
                if label_id not in self.labels:
                    self._errors.append(f"Endpoint {path} {method}: label {label_id!r} does not exist")
                else:
                    leg = self.labels[label_id].get("legacy", {})
                    steps = leg.get("steps", [])
                    j_count = sum(1 for s in steps if s.get("op") == "J")
                    if j_count != 1:
                        self._errors.append(f"Endpoint {path} {method} label {label_id}: must have exactly one J (has {j_count})")
                    return_var = ep.get("return_var")
                    if return_var and j_count == 1:
                        j_var = next((s.get("var") for s in steps if s.get("op") == "J"), None)
                        if j_var and j_var != return_var:
                            self._errors.append(f"Endpoint {path} {method}: E return_var {return_var!r} does not match J var {j_var!r}")

            # Collect all label targets referenced by control-flow ops.
            for lid, body in self.labels.items():
                steps = body.get("legacy", {}).get("steps", [])
                for s in steps:
                    opn = s.get("op")
                    if opn == "If":
                        t = self._norm_lid(s.get("then"))
                        e = self._norm_lid(s.get("else"))
                        if t:
                            targeted_labels.add(t)
                        if e:
                            targeted_labels.add(e)
                    elif opn == "Err":
                        h = self._norm_lid(s.get("handler"))
                        if h:
                            targeted_labels.add(h)
                    elif opn == "Call":
                        c = self._norm_lid(s.get("label"))
                        if c:
                            targeted_labels.add(c)

            # Every targeted label should exist, have legacy.steps, and end with exactly one J.
            for tl in sorted(targeted_labels):
                body = self.labels.get(tl)
                if not body:
                    self._errors.append(f"Targeted label {tl!r} does not exist")
                    continue
                steps = body.get("legacy", {}).get("steps", [])
                if not steps:
                    self._errors.append(f"Targeted label {tl!r} has no legacy.steps")
                    continue
                j_steps = [s for s in steps if s.get("op") == "J"]
                if len(j_steps) != 1:
                    self._errors.append(f"Targeted label {tl!r} must contain exactly one J (has {len(j_steps)})")
                    continue
                if steps[-1].get("op") != "J":
                    self._errors.append(f"Targeted label {tl!r} must end in J")

            # Optional strict reachability over label references from endpoint roots.
            if self.strict_reachability and endpoint_labels:
                graph: Dict[str, set] = {}
                for lid, body in self.labels.items():
                    ls = body.get("legacy", {}).get("steps", [])
                    nxt: set = set()
                    for s in ls:
                        if s.get("op") == "If":
                            for x in (s.get("then"), s.get("else")):
                                nx = self._norm_lid(x)
                                if nx:
                                    nxt.add(nx)
                        elif s.get("op") == "Err":
                            nx = self._norm_lid(s.get("handler"))
                            if nx:
                                nxt.add(nx)
                        elif s.get("op") == "Call":
                            nx = self._norm_lid(s.get("label"))
                            if nx:
                                nxt.add(nx)
                    graph[lid] = nxt
                reachable: set = set()
                stack = list(endpoint_labels)
                while stack:
                    cur = stack.pop()
                    if cur in reachable:
                        continue
                    reachable.add(cur)
                    for nx in graph.get(cur, set()):
                        if nx not in reachable:
                            stack.append(nx)
                for lid in self.labels.keys():
                    if lid == "_anon":
                        continue
                    if lid not in reachable:
                        self._errors.append(f"Label {lid!r} is unreachable from endpoint roots")

        return {
            "source": {"text": source_text, "lines": source_lines},
            "cst": {"lines": cst_lines},
            "services": self.services,
            "types": self.types,
            "labels": self.labels,
            "crons": self.crons,
            "config": self.config,
            "observability": self.observability,
            "deploy": self.deploy,
            "limits": self.limits,
            "roles": self.roles,
            "allow": self.allow,
            "audit": self.audit,
            "admin": self.admin,
            "desc": self.desc,
            "runbooks": self.runbooks,
            "ver": self.ver,
            "compat": self.compat,
            "tests": self.tests,
            "api": self.api_opts,
            "rag": self.rag,
            "meta": self.meta,
            "errors": self._errors,
            "stats": {
                "lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
                "ops": parsed_ops,
            },
        }

    def emit_source_exact(self, ir: Dict[str, Any]) -> str:
        """Return the stored original source text (byte-for-byte), not reconstructed."""
        src = ir.get("source") or {}
        return src.get("text", "")

    def emit_react(self, ir: Dict[str, Any]) -> str:
        fe = ir["services"].get("fe", {})
        uis = fe.get("ui", {})
        states = fe.get("states", {})
        jsx = "// AINL emitted React/TSX\nimport React, { useState } from 'react';\n\n"
        for ui_name, props in uis.items():
            state_list = states.get(ui_name, [("data", "any")])
            jsx += f"export const {ui_name}: React.FC = () => {{\n"
            for var, typ in state_list:
                ts_typ = normalize_type(typ)
                setter = "set" + (var[:1].upper() + var[1:] if var else "Data")
                default = default_value_for_type(ts_typ)
                jsx += f"  const [{var}, {setter}] = useState<{ts_typ}>({default});\n"
            jsx += "  return (\n    <div className=\"dashboard\">\n"
            jsx += f"      <h1>{ui_name}</h1>\n"
            if props:
                comp = props[0]
                data_prop = props[1] if len(props) > 1 else (props[0] if props[0].islower() or not props[0][:1].isupper() else "data")
                if comp[0].islower():
                    comp = "DataTable"
                    data_prop = props[0]
                jsx += f"      <{comp} data={{{data_prop}}} />\n"
            jsx += "    </div>\n  );\n};\n\n"
        return jsx

    def _path_to_var(self, ir: Dict[str, Any]) -> Dict[Tuple[str, str], str]:
        """Map (path, method) -> return var. Prefer E.return_var; else label exits[0].var; else infer from legacy.steps J."""
        path_var: Dict[Tuple[str, str], str] = {}
        core = ir.get("services", {}).get("core", {})
        eps = core.get("eps", {})
        labels = ir.get("labels", {})
        for path, method, ep in _iter_eps(eps):
            key = (path, self._dsl_method(method or ep.get("method", "G")))
            if ep.get("return_var"):
                path_var[key] = ep["return_var"]
                continue
            label_id = ep.get("label_id") or ep.get("tgt", "")
            if isinstance(label_id, str) and label_id.startswith("L"):
                label_id = label_id[1:]
            if ":" in str(label_id):
                label_id = str(label_id).split(":")[-1]
            lab = labels.get(label_id, {})
            exits = lab.get("exits", [])
            if exits:
                path_var[key] = exits[0].get("var", "data")
                continue
            steps = lab.get("legacy", {}).get("steps", [])
            for s in steps:
                if s.get("op") == "J":
                    path_var[key] = s.get("var", "data")
                    break
        return path_var

    def _path_to_entity(self, ir: Dict[str, Any]) -> Dict[Tuple[str, str], str]:
        """Map (path, method) -> entity type from E/L/R. Uses explicit label_id when set."""
        path_entity: Dict[Tuple[str, str], str] = {}
        core = ir.get("services", {}).get("core", {})
        eps = core.get("eps", {})
        labels = ir.get("labels", {})
        for path, method, ep in _iter_eps(eps):
            label_id = ep.get("label_id") or ep.get("tgt", "")
            if isinstance(label_id, str) and label_id.startswith("L"):
                label_id = label_id[1:]
            if ":" in str(label_id):
                label_id = str(label_id).split(":")[-1]
            steps = labels.get(label_id, {}).get("legacy", {}).get("steps", [])
            key = (path, self._dsl_method(method or ep.get("method", "G")))
            for s in steps:
                if s.get("op") == "R" and s.get("entity"):
                    path_entity[key] = s["entity"]
                    break
        return path_entity

    def emit_react_browser(self, ir: Dict[str, Any]) -> str:
        """Emit React with routes (hash), layout, forms, tables, events; fetches API."""
        fe = ir["services"].get("fe", {})
        uis = fe.get("ui", {})
        states = fe.get("states", {})
        routes = fe.get("routes", [])
        layouts = fe.get("layouts", {})
        forms = fe.get("forms", {})
        tables = fe.get("tables", {})
        events = fe.get("events", [])
        core_path = (ir["services"].get("core", {}).get("path") or "/api").strip("/") or "api"
        api_base = f"/{core_path}"
        path_to_var = self._path_to_var(ir)

        tokens = fe.get("tokens", {})
        theme = fe.get("theme", "")
        i18n_map = fe.get("i18n", {}) or fe.get("copy", {})
        a11y_map = fe.get("a11y", {})
        retry_cfg = fe.get("retry", {})
        help_map = fe.get("help", {})

        jsx = "const { useState, useEffect } = React;\n\n"
        if tokens:
            jsx += "const designTokens = " + json.dumps(tokens) + ";\n"
        if theme:
            jsx += "document.body.className = '" + theme + "';\n"
        if i18n_map:
            jsx += "const i18n = " + json.dumps(i18n_map) + ";\n"
        if retry_cfg:
            count = retry_cfg.get("count", "3")
            backoff = retry_cfg.get("backoff_ms", "1000")
            jsx += "async function fetchWithRetry(url, opts) { for (let i = 0; i < " + str(count) + "; i++) { try { const r = await fetch(url, opts); if (r.ok) return r; } catch (e) {} await new Promise(r => setTimeout(r, " + str(backoff) + ")); } return fetch(url, opts); }\n"
        jsx += "const DataTable = ({ data, columns }) => (\n"
        jsx += "  <table><tbody>{((data || []).map((row, i) => {\n"
        jsx += "    const isObj = row && typeof row === 'object' && !Array.isArray(row);\n"
        jsx += "    const cols = columns || (isObj ? Object.keys(row) : ['value']);\n"
        jsx += "    return <tr key={i}>{cols.map(c => <td key={c}>{isObj ? row[c] : String(row)}</td>)}</tr>;\n"
        jsx += "  }))}</tbody></table>\n);\n\n"
        jsx += "const DataForm = ({ name, fields, onSubmit }) => (\n"
        jsx += "  <form onSubmit={e => { e.preventDefault(); onSubmit(new FormData(e.target)); }}>\n"
        jsx += "    { (fields || []).map(f => <label key={f}>{f}<input name={f} /></label>) }\n"
        jsx += "    <button type=\"submit\">Submit</button>\n  </form>\n);\n\n"

        event_handlers = {}
        for ev in events:
            comp, event_type, target = ev.get("component"), ev.get("event", "click"), ev.get("target", "")
            if target.startswith("/"):
                event_handlers.setdefault(comp, {})[event_type] = (
                    f"() => fetch('{api_base}{target}', {{ method: 'POST' }}).then(r => r.json()).then(console.log)"
                )
            else:
                event_handlers.setdefault(comp, {})[event_type] = (
                    f"() => fetch('{api_base}/' + '{target}'.toLowerCase(), {{ method: 'POST' }}).then(r => r.json()).then(console.log)"
                )

        bindings_by_ui = fe.get("bindings", {})
        for ui_name, props in uis.items():
            state_list = list(states.get(ui_name, [("data", "any")]))
            state_vars = [v for v, _ in state_list]
            single_ep = len(path_to_var) == 1
            single_ep_binding = next(iter(path_to_var.items())) if single_ep else None
            for p in props:
                if isinstance(p, str) and p.islower() and p in path_to_var.values() and p not in state_vars:
                    state_list.append((p, "any"))
                    state_vars.append(p)
            ui_bindings = bindings_by_ui.get(ui_name, [])
            if ui_bindings:
                for b in ui_bindings:
                    var = b.get("var", "data")
                    if var not in state_vars:
                        state_vars.append(var)
                        state_list.append((var, "any"))
            else:
                if single_ep_binding is not None:
                    (_path, _method), ret_var = single_ep_binding
                    if ret_var not in state_vars:
                        state_vars.append(ret_var)
                        state_list.append((ret_var, "any"))
            jsx += f"const {ui_name} = () => {{\n"
            for var, typ in state_list:
                setter = "set" + (var[:1].upper() + var[1:] if var else "Data")
                default = default_value_for_type(normalize_type(typ))
                jsx += f"  const [{var}, {setter}] = useState({default});\n"
            fetch_fn = "fetchWithRetry" if retry_cfg else "fetch"
            if ui_bindings:
                for b in ui_bindings:
                    path, method, var = b.get("path", ""), b.get("method", "G"), b.get("var", "data")
                    meth = self._http_method_upper(method or "G")
                    jsx += f"  useEffect(() => {{\n"
                    jsx += f"    {fetch_fn}('{api_base}{path}', {{ method: '{meth}' }}).then(r => r.json()).then(d => set{var[:1].upper() + var[1:]}(d.data ?? d));\n"
                    jsx += f"  }}, []);\n"
            else:
                if single_ep_binding is not None:
                    (path, method), ret_var = single_ep_binding
                    meth = self._http_method_upper(method or "G")
                    jsx += f"  useEffect(() => {{\n"
                    jsx += f"    {fetch_fn}('{api_base}{path}', {{ method: '{meth}' }}).then(r => r.json()).then(d => set{ret_var[:1].upper() + ret_var[1:]}(d.data ?? d));\n"
                    jsx += f"  }}, []);\n"
            ev_obj = event_handlers.get(ui_name, {})
            onClick = ev_obj.get("click")
            aria = a11y_map.get(ui_name, "")
            jsx += "  return (\n    <div className=\"dashboard\"" + (f' aria-label="{aria}"' if aria else "") + ">\n"
            jsx += f"      <h1>{ui_name}</h1>\n"
            if props:
                comp = props[0]
                data_prop = props[1] if len(props) > 1 else (props[0] if props[0].islower() or not props[0][:1].isupper() else "data")
                if comp[0].islower():
                    comp = "DataTable"
                    data_prop = props[0]
                cols = tables.get(ui_name, {}).get("columns", []) if isinstance(tables.get(ui_name), dict) else []
                if comp == "DataTable" and cols:
                    jsx += f"      <DataTable data={{{data_prop}}} columns={{{json.dumps(cols)}}} />\n"
                else:
                    jsx += f"      <{comp} data={{{data_prop}}} />\n"
            if onClick:
                jsx += f"      <button onClick={{ {onClick} }}>{ui_name}</button>\n"
            jsx += "    </div>\n  );\n};\n\n"

        if routes:
            route_list = routes
            route_map = {r["path"]: r["ui"] for r in route_list}
        else:
            first_ui = next(iter(uis.keys()), "Dashboard")
            route_map = {"/": first_ui}
        first_ui = next(iter(uis.keys()), "Dashboard")

        layout_name = next(iter(layouts.keys()), "Shell") if layouts else None
        if layout_name:
            jsx += f"const {layout_name} = ({{ children }}) => (\n"
            jsx += "  <div className=\"layout\"><aside>Nav</aside><main>{children}</main></div>\n);\n\n"

        comp_map = ", ".join([f'"{k}": {k}' for k in uis.keys()])
        jsx += "const App = () => {\n"
        jsx += "  const [path, setPath] = useState(() => (window.location.hash || '#/').slice(1) || '/');\n"
        jsx += "  useEffect(() => { const onHash = () => setPath((window.location.hash || '#/').slice(1) || '/'); window.addEventListener('hashchange', onHash); onHash(); return () => window.removeEventListener('hashchange', onHash); }, []);\n"
        jsx += "  const R = " + json.dumps(route_map) + ";\n"
        jsx += "  const Comps = { " + comp_map + " };\n"
        jsx += "  const Page = Comps[R[path]] || " + first_ui + ";\n"
        jsx += "  const nav = " + json.dumps(list(route_map.keys())) + ".map(p => <a key={p} href={'#'+p}>{p}</a>);\n"
        if layout_name:
            jsx += f"  return <{layout_name}><nav>{{nav}}</nav><main><Page /></main></{layout_name}>;\n" + "};\n\n"
        else:
            jsx += "  return <div><nav>{nav}</nav><Page /></div>;\n};\n\n"
        jsx += "ReactDOM.render(<App />, document.getElementById('root'));\n"
        return jsx

    def emit_prisma_schema(self, ir: Dict[str, Any]) -> str:
        out = "// Prisma schema generated from D (Data) ops\n\ngenerator client {\n  provider = \"prisma-client-js\"\n}\n\ndatasource db {\n  provider = \"postgresql\"\n  url      = env(\"DATABASE_URL\")\n}\n\n"
        for name, data in ir["types"].items():
            out += f"model {name} {{\n"
            fields = data.get("fields", {})
            if "id" not in fields and "id:I" not in str(fields):
                out += "  id    Int     @id @default(autoincrement())\n"
            for fname, typ in fields.items():
                prisma_typ = normalize_type(typ)
                out += f"  {fname}  {prisma_typ}\n"
            out += "}\n\n"
        return out

    def _http_method(self, m: str) -> str:
        return {"G": "get", "P": "post", "U": "put", "D": "delete", "L": "get"}.get(m.upper(), m.lower())

    def _http_method_upper(self, m: str) -> str:
        mm = (m or "G").upper()
        return {"G": "GET", "P": "POST", "U": "PUT", "D": "DELETE", "L": "GET"}.get(mm, mm)

    def _dsl_method(self, m: str) -> str:
        """Normalize method token to DSL letter (G/P/U/D)."""
        mm = (m or "G").upper()
        if mm in ("G", "P", "U", "D", "L"):
            return "G" if mm == "L" else mm
        return {"GET": "G", "POST": "P", "PUT": "U", "DELETE": "D"}.get(mm, "G")

    def emit_python_api(self, ir: Dict[str, Any]) -> str:
        py = "from fastapi import FastAPI\napp = FastAPI()\n\n"
        for srv, data in ir["services"].items():
            if "eps" not in data:
                continue
            for path, method, ep in _iter_eps(data["eps"]):
                seg = path.strip("/").replace("/", "_") or "root"
                meth = self._http_method(method or ep.get("method", "G"))
                fn_name = f"{meth}_{seg}"
                py += f"@app.{meth}('{path}')\n"
                py += f"def {fn_name}():\n"
                py += f"    # Exec {ep.get('tgt', path)}\n"
                py += "    return {\"data\": []}\n\n"
        return py

    def emit_mt5(self, ir: Dict[str, Any]) -> str:
        code = "// MT5 Expert Advisor stub — generated from .lang\n"
        code += "#property strict\n\n"
        code += "input int   Multiplier = 1;\n"
        code += "input double LotSize = 0.1;\n"
        for typ, data in ir.get("types", {}).items():
            for field, t in data.get("fields", {}).items():
                code += f"// {typ}.{field} : {t}\n"
        code += "\nint OnInit()\n{\n  return(INIT_SUCCEEDED);\n}\n\n"
        code += "void OnTick()\n{\n"
        code += "  if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;\n"
        code += "  // TODO: signals from parsed services / symbols\n"
        code += "  // MqlTick tick; SymbolInfoTick(_Symbol, tick);\n"
        code += "}\n\nvoid OnDeinit(const int reason) {}\n"
        return code

    def emit_python_scraper(self, ir: Dict[str, Any]) -> str:
        defs = ir["services"].get("scrape", {}).get("defs", {})
        if not defs:
            return "# No Sc scrape definitions in IR\nimport requests\n"
        code = "import requests\nfrom bs4 import BeautifulSoup\n\n"
        for name, defn in defs.items():
            url = defn.get("url", "")
            selectors = defn.get("selectors", {})
            code += f"def scrape_{name}():\n"
            code += f"    resp = requests.get('{url}')\n"
            code += "    soup = BeautifulSoup(resp.text, 'html.parser')\n"
            for var_name, css_selector in selectors.items():
                code += f"    el = soup.select_one('{css_selector}')\n"
                code += f"    {var_name} = el.get_text(strip=True) if el else None\n"
            fields = ", ".join([f"'{v}': {v}" for v in selectors.keys()])
            code += f"    return {{ {fields} }}\n\n"
        return code

    def emit_cron_stub(self, ir: Dict[str, Any]) -> str:
        crons = ir.get("crons", [])
        if not crons:
            return "# No Cr cron definitions\n"
        py = "# Cron stubs (use APScheduler or Celery Beat)\nfrom datetime import datetime\n\n"
        for c in crons:
            py += f"def run_{c['label']}():\n"
            py += f"    # Schedule: {c['expr']}\n"
            py += "    pass\n\n"
        return py

    def emit_server(self, ir: Dict[str, Any]) -> str:
        """Emit server that runs labels via ExecutionEngine + pluggable adapters."""
        core = ir["services"].get("core", {})
        api_prefix = (core.get("path") or "/api").strip("/") or "api"
        api_prefix = "/" + api_prefix

        py = '"""Web server from AI-Native Lang: real runtime (R/P/Sc via adapters) + static + logging + rate limit."""\n'
        py += "import json\nimport sys\nimport time\nimport uuid\nimport os\nfrom pathlib import Path\nfrom collections import defaultdict\n\n"
        py += "# Allow importing runtime + adapters (same dir in Docker, else repo root)\n"
        py += "_dir = Path(__file__).resolve().parent\n"
        py += "_root = _dir if (_dir / 'runtime.py').exists() else _dir.parent.parent.parent\n"
        py += "if str(_root) not in sys.path:\n    sys.path.insert(0, str(_root))\n\n"
        py += "from fastapi import FastAPI, Request\nfrom fastapi.middleware.cors import CORSMiddleware\n"
        py += "from fastapi.staticfiles import StaticFiles\nfrom starlette.middleware.base import BaseHTTPMiddleware\n\n"
        py += "from runtime import ExecutionEngine\nfrom adapters import mock_registry\n\n"
        py += "# Load IR (emitted with server); use real adapters by replacing mock_registry\n"
        py += "_ir_path = Path(__file__).resolve().parent / \"ir.json\"\n"
        py += "with open(_ir_path) as f:\n    _ir = json.load(f)\n"
        py += "_registry = mock_registry(_ir.get(\"types\"))\n"
        py += "_engine = ExecutionEngine(_ir, _registry)\n\n"
        # Env validation at startup (config.env)
        config = ir.get("config", {})
        env_list = config.get("env", [])
        if env_list:
            py += "# Validate required env at startup\n"
            py += "for _e in " + repr(env_list) + ":\n"
            py += "    if _e.get(\"required\") and not os.environ.get(_e.get(\"name\")):\n"
            py += "        raise RuntimeError(f\"Missing required env: {_e.get('name')}\")\n\n"
        # Per-path rate limits
        limits = ir.get("limits", {})
        per_path = limits.get("per_path", {})
        if per_path:
            py += "class PerPathRateLimitMiddleware(BaseHTTPMiddleware):\n"
            py += "    def __init__(self, app, limits_map):\n"
            py += "        super().__init__(app)\n"
            py += "        self.limits = limits_map\n"
            py += "        self.window_start = defaultdict(lambda: defaultdict(float))\n"
            py += "        self.count = defaultdict(lambda: defaultdict(int))\n\n"
            py += "    async def dispatch(self, request: Request, call_next):\n"
            py += "        path = request.url.path\n"
            py += "        rpm = self.limits.get(path)\n"
            py += "        if not rpm:\n"
            py += "            return await call_next(request)\n"
            py += "        rpm = int(rpm)\n"
            py += "        client = request.client.host if request.client else \"unknown\"\n"
            py += "        key = path + \"|\" + client\n"
            py += "        now = time.time()\n"
            py += "        if now - self.window_start[path][client] > 60:\n"
            py += "            self.window_start[path][client] = now\n"
            py += "            self.count[path][client] = 0\n"
            py += "        self.count[path][client] += 1\n"
            py += "        if self.count[path][client] > rpm:\n"
            py += "            from starlette.responses import JSONResponse\n"
            py += "            return JSONResponse(status_code=429, content={\"error\": \"rate limit exceeded\"})\n"
            py += "        return await call_next(request)\n\n"
        obs = ir.get("observability", {})
        trace_enabled = obs.get("trace", False)
        py += "_metrics = defaultdict(int)\n"
        py += "_trace_enabled = " + ("True" if trace_enabled else "False") + "\n\n"
        py += "class LoggingMiddleware(BaseHTTPMiddleware):\n"
        py += "    async def dispatch(self, request: Request, call_next):\n"
        py += "        req_id = str(uuid.uuid4())[:8]\n"
        py += "        trace_id = req_id if _trace_enabled else None\n"
        py += "        start = time.perf_counter()\n"
        py += "        response = await call_next(request)\n"
        py += "        duration_ms = (time.perf_counter() - start) * 1000\n"
        py += "        # Never log Authorization or other secret headers (fix #11).\n"
        py += "        log = {\"request_id\": req_id, \"method\": request.method, \"path\": request.url.path, \"status\": response.status_code, \"duration_ms\": round(duration_ms, 2)}\n"
        py += "        if trace_id:\n            log[\"trace_id\"] = trace_id\n"
        if ir.get("audit"):
            py += "        log[\"audit\"] = True\n"
            py += "        log[\"role\"] = request.headers.get(\"X-Role\")\n"
        py += "        _metrics[\"requests_total\"] += 1\n"
        py += "        print(json.dumps(log))\n"
        py += "        return response\n\n"
        py += "class RateLimitMiddleware(BaseHTTPMiddleware):\n"
        py += "    def __init__(self, app, requests_per_minute: int = 0):\n"
        py += "        super().__init__(app)\n"
        py += "        self.rpm = requests_per_minute\n"
        py += "        self.window_start = defaultdict(float)\n"
        py += "        self.count = defaultdict(int)\n\n"
        py += "    async def dispatch(self, request: Request, call_next):\n"
        py += "        if self.rpm <= 0:\n"
        py += "            return await call_next(request)\n"
        py += "        client = request.client.host if request.client else \"unknown\"\n"
        py += "        now = time.time()\n"
        py += "        if now - self.window_start[client] > 60:\n"
        py += "            self.window_start[client] = now\n"
        py += "            self.count[client] = 0\n"
        py += "        self.count[client] += 1\n"
        py += "        if self.count[client] > self.rpm:\n"
        py += "            from starlette.responses import JSONResponse\n"
        py += "            return JSONResponse(status_code=429, content={\"error\": \"rate limit exceeded\"})\n"
        py += "        return await call_next(request)\n\n"
        py += "app = FastAPI(title=\"Lang Server\")\n"
        py += "_rate_limit = int(os.environ.get(\"RATE_LIMIT\", \"0\"))\n"
        if per_path:
            py += "app.add_middleware(PerPathRateLimitMiddleware, limits_map=" + repr(per_path) + ")\n"
        py += "app.add_middleware(RateLimitMiddleware, requests_per_minute=_rate_limit)\n"
        py += "app.add_middleware(LoggingMiddleware)\n"
        py += "app.add_middleware(CORSMiddleware, allow_origins=[\"*\"], allow_methods=[\"*\"], allow_headers=[\"*\"])\n\n"
        py += "def _run_label(lid):\n    r = _engine.run(lid); return {\"data\": r if r is not None else []}\n\n"
        py += "api = FastAPI()\n\n"

        auth = ir["services"].get("auth")
        allow_list = ir.get("allow", [])
        roles_list = ir.get("roles", [])
        audit_cfg = ir.get("audit", {})
        deploy_flags = ir.get("deploy", {}).get("flags", [])

        if auth:
            header_name = auth.get("arg", "Authorization")
            py += "from fastapi import Depends, HTTPException, Request\n\n"
            py += "def _auth_dep(request: Request):\n"
            py += f"    val = request.headers.get(\"{header_name}\")\n"
            py += "    if not val:\n"
            py += "        raise HTTPException(status_code=401, detail=\"Missing auth header\")\n"
            py += "    return val\n\n"

        if allow_list and roles_list:
            allow_with_full_path = []
            for a in allow_list:
                if a.get("path"):
                    allow_with_full_path.append({"role": a.get("role"), "path": api_prefix.rstrip("/") + a["path"], "method": a.get("method", "GET")})
            py += "_allow_by_path = " + json.dumps(allow_with_full_path) + "\n"
            py += "def _rbac_dep(request: Request):\n"
            py += "    role = request.headers.get(\"X-Role\", \"\")\n"
            py += "    path = request.url.path\n"
            py += "    method = request.method\n"
            py += "    for a in _allow_by_path:\n"
            py += "        if a.get(\"path\") == path and (not a.get(\"method\") or a.get(\"method\") == method):\n"
            py += "            if role == a.get(\"role\"):\n                return\n"
            py += "    raise HTTPException(status_code=403, detail=\"Forbidden\")\n\n"

        if audit_cfg:
            py += "_audit_retention_days = " + str(audit_cfg.get("retention_days", 90)) + "\n"
            py += "def _audit_log(method, path, status, role=None):\n"
            py += "    print(json.dumps({\"audit\": True, \"method\": method, \"path\": path, \"status\": status, \"role\": role}))\n\n"

        deps = []
        if auth:
            deps.append("Depends(_auth_dep)")
        if allow_list and roles_list:
            deps.append("Depends(_rbac_dep)")
        dep_str = ", dependencies=[" + ", ".join(deps) + "]" if deps else ""

        py += "def _iter_eps(eps):\n"
        py += "    out = []\n"
        py += "    for path, val in eps.items():\n"
        py += "        if not isinstance(val, dict): continue\n"
        py += "        if \"label_id\" in val or \"method\" in val:\n"
        py += "            out.append((path, val.get(\"method\", \"G\"), val))\n"
        py += "        else:\n"
        py += "            for method, ep in val.items():\n"
        py += "                if isinstance(ep, dict):\n"
        py += "                    out.append((path, method, ep))\n"
        py += "    return out\n\n"

        for srv, data in ir["services"].items():
            if "eps" not in data:
                continue
            for path, method, ep in _iter_eps(data["eps"]):
                meth = self._http_method(method or ep.get("method", "G"))
                label_id = ep.get("label_id", "")
                seg = path.strip("/").replace("/", "_") or "root"
                fn_name = f"{meth}_{seg}"
                py += f"@api.{meth}('{path}'{dep_str})\n"
                py += f"def {fn_name}():\n"
                py += f"    return _run_label('{label_id}')\n\n"

        py += "@api.get(\"/health\")\n"
        py += "def health():\n"
        py += "    return {\"status\": \"ok\"}\n\n"
        py += "@api.get(\"/ready\")\n"
        py += "def ready():\n"
        py += "    return {\"ready\": True}\n\n"

        py += f"app.mount(\"{api_prefix}\", api)\n\n"
        py += "# Static: do not write user-provided content to static_dir (fix #10).\n"
        py += "static_dir = Path(__file__).resolve().parent / \"static\"\n"
        py += "static_dir.mkdir(exist_ok=True)\n"
        py += "if static_dir.exists():\n"
        py += "    app.mount(\"/\", StaticFiles(directory=str(static_dir), html=True), name=\"static\")\n\n"
        py += "if __name__ == \"__main__\":\n"
        py += "    import uvicorn\n"
        py += "    uvicorn.run(app, host=\"0.0.0.0\", port=8765)\n"
        return py

    def emit_ir_json(self, ir: Dict[str, Any]) -> str:
        """Emit IR as JSON for the server runtime (labels, services, types, crons)."""

        # Ensure all values are JSON-serializable (tuples -> lists)
        def to_jsonable(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: to_jsonable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [to_jsonable(x) for x in obj]
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            return str(obj)

        return json.dumps(to_jsonable(ir), indent=2)

    def _openapi_type(self, shorthand: str) -> str:
        """Map AINL type shorthand to OpenAPI/JSON Schema type."""
        s = (shorthand or "").strip()
        if s.startswith("A[") and s.endswith("]"):
            return "array"
        if s in ("I", "i"):
            return "integer"
        if s == "J":
            return "object"
        if s in ("F", "S", "s", "B", "D"):
            return "number" if s == "F" else "string"
        if s.startswith("E["):
            return "string"
        return "string"

    def _openapi_schema_for_type(self, shorthand: str, types: Dict[str, Any]) -> Dict[str, Any]:
        """Build OpenAPI schema, preserving A[Type] inner typing and model refs."""
        s = (shorthand or "").strip()
        if s.startswith("A[") and s.endswith("]"):
            inner = s[2:-1].strip()
            return {"type": "array", "items": self._openapi_schema_for_type(inner, types)}
        if s == "J":
            return {"type": "object", "additionalProperties": True}
        if s in types:
            return {"$ref": f"#/components/schemas/{s}"}
        return {"type": self._openapi_type(s)}

    def emit_openapi(self, ir: Dict[str, Any]) -> str:
        """Emit OpenAPI 3.0 JSON from E + D for API docs, codegen, gateways."""
        core = ir["services"].get("core", {})
        api_path_prefix = (core.get("path") or "/api").strip("/") or "api"
        base_path = f"/{api_path_prefix}"
        path_to_entity = self._path_to_entity(ir)
        types = ir.get("types", {})

        schemas = {}
        for name, data in types.items():
            props = {}
            for f, t in data.get("fields", {}).items():
                props[f] = self._openapi_schema_for_type(t, types)
            schemas[name] = {"type": "object", "properties": props}
        schemas["DataResponse"] = {
            "type": "object",
            "properties": {
                "data": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "object"}},
                        {"type": "object"},
                    ]
                }
            },
        }

        paths = {}
        for srv, data in ir.get("services", {}).items():
            if "eps" not in data:
                continue
            for path, method, ep in _iter_eps(data["eps"]):
                meth = self._http_method(method or ep.get("method", "G"))
                full_path = base_path + path
                if full_path not in paths:
                    paths[full_path] = {}
                dsl_method = self._dsl_method(method or ep.get("method", "G"))
                entity = path_to_entity.get((path, dsl_method), "")
                if not entity and ep.get("return_type"):
                    rt = ep["return_type"]
                    entity = str(rt).replace("A[", "").rstrip("]") if isinstance(rt, str) else ""
                item_schema: Dict[str, Any] = {"type": "object"}
                if ep.get("return_type"):
                    rt_schema = self._openapi_schema_for_type(ep.get("return_type"), types)
                    if rt_schema.get("type") == "array":
                        item_schema = rt_schema.get("items", {"type": "object"})
                    else:
                        item_schema = rt_schema
                elif entity in schemas:
                    item_schema = {"$ref": f"#/components/schemas/{entity}"}
                desc = ep.get("description") or ep.get("meta", {}).get("description")
                desc_endpoints = ir.get("desc", {}).get("endpoints", {})
                api_deprecate = ir.get("api", {}).get("deprecate", [])
                deprec = next((d for d in api_deprecate if d.get("path") == path), None)
                op_spec = {
                    "summary": ep.get("tgt", path),
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "data": {
                                                "oneOf": [
                                                    {"type": "array", "items": item_schema},
                                                    item_schema,
                                                ],
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
                if desc or desc_endpoints.get(path):
                    op_spec["description"] = desc or desc_endpoints.get(path, "")
                if deprec:
                    op_spec["deprecated"] = True
                paths[full_path][meth] = op_spec

        paths[base_path + "/health"] = {
            "get": {"summary": "Health", "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object", "properties": {"status": {"type": "string"}}}}}}}}
        }
        paths[base_path + "/ready"] = {
            "get": {"summary": "Readiness", "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object", "properties": {"ready": {"type": "boolean"}}}}}}}}
        }
        doc = {
            "openapi": "3.0.0",
            "info": {"title": "AINL API", "version": "1.0.0"},
            "paths": paths,
            "components": {"schemas": schemas},
        }
        return json.dumps(doc, indent=2)

    def emit_dockerfile(self, ir: Dict[str, Any]) -> str:
        """Emit Dockerfile for the AINL server. Run from server dir: docker compose up --build"""
        return """# AINL emitted server (build from server dir: docker compose up --build)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt server.py ir.json runtime.py ./
COPY adapters ./adapters/
COPY static ./static/
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8765
ENV PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
"""

    def emit_docker_compose(self, ir: Dict[str, Any]) -> str:
        """Emit docker-compose.yml (api + optional db)."""
        has_db = bool(ir.get("types"))
        yml = """# AINL emitted stack
services:
  api:
    build: .
    ports:
      - "8765:8765"
    environment:
      - DATABASE_URL=${DATABASE_URL:-postgresql://postgres:postgres@db:5432/ainl}
"""
        if has_db:
            yml += """
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ainl
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
"""
        return yml

    def emit_k8s(self, ir: Dict[str, Any], name: str = "ainl-api", replicas: int = 1, with_ingress: bool = False) -> str:
        """Emit Kubernetes Deployment + Service (and optional Ingress) for the AINL server."""
        yml = f"""# AINL emitted K8s (apply: kubectl apply -f -)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: api
        image: {name}:latest
        ports:
        - containerPort: 8765
        env:
        - name: PYTHONUNBUFFERED
          value: "1"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8765
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 8765
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
  - port: 80
    targetPort: 8765
"""
        if with_ingress:
            yml += f"""
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}
spec:
  rules:
  - host: {name}.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {name}
            port:
              number: 80
"""
        return yml

    def emit_next_api_routes(self, ir: Dict[str, Any]) -> Dict[str, str]:
        """Emit Next.js API route handlers (pages/api/*). Proxies to BACKEND_URL or returns mock."""
        core = ir["services"].get("core", {})
        api_prefix = (core.get("path") or "/api").strip("/") or "api"
        out = {}
        out["_api_prefix"] = api_prefix
        for srv, data in ir.get("services", {}).items():
            if "eps" not in data:
                continue
            for path, method, ep in _iter_eps(data["eps"]):
                meth = self._http_method(method or ep.get("method", "G"))
                seg = path.strip("/").replace("/", "_") or "root"
                fn = f"pages/api/{seg}_{meth.upper()}.ts"
                content = f"""// AINL emitted Next.js API route: {meth.upper()} {path}
import type {{ NextApiRequest, NextApiResponse }} from 'next';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8765';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {{
  if (req.method !== '{meth.upper()}') return res.status(405).end();
  try {{
    const r = await fetch(`${{BACKEND_URL}}/{api_prefix}{path}`, {{ method: '{meth.upper()}' }});
    const data = await r.json();
    res.status(200).json(data);
  }} catch (e) {{
    res.status(502).json({{ error: 'Backend unreachable', data: [] }});
  }}
}}
"""
                out[fn] = content
        out["pages/api/health.ts"] = """// AINL health
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(_req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({ status: 'ok' });
}
"""
        out["pages/api/ready.ts"] = """// AINL readiness
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(_req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({ ready: true });
}
"""
        return out

    def emit_vue_browser(self, ir: Dict[str, Any]) -> str:
        """Emit Vue 3 (Composition API) single-file app; hash router, fetch API."""
        fe = ir["services"].get("fe", {})
        uis = fe.get("ui", {})
        routes = fe.get("routes", [])
        path_to_var = self._path_to_var(ir)
        api_base = "/" + ((ir["services"].get("core", {}).get("path") or "/api").strip("/") or "api")
        route_map = {r["path"]: r["ui"] for r in routes} if routes else {"/": next(iter(uis.keys()), "Dashboard")}
        var_paths = {v: (p, m) for (p, m), v in path_to_var.items()}
        lines = [
            "<script setup>",
            "import { ref, onMounted } from 'vue'",
            "const path = ref(typeof location !== 'undefined' ? (location.hash || '#/').slice(1) || '/' : '/')",
            "const R = " + json.dumps(route_map),
            "const nav = Object.keys(R)",
        ]
        for var, (p, m) in var_paths.items():
            meth = self._http_method_upper(m or "G")
            lines.append(f"const {var} = ref([])")
            lines.append(f"onMounted(() => fetch('{api_base}{p}', {{ method: '{meth}' }}).then(r => r.json()).then(d => {{ {var}.value = d.data || [] }}))")
        lines.append("</script>")
        lines.append("<template>")
        lines.append("  <nav><a v-for=\"p in nav\" :key=\"p\" :href=\"'#'+p\">{{ p }}</a></nav>")
        default_var = list(var_paths.keys())[0] if var_paths else "data"
        for pkey, ui_name in route_map.items():
            disp_var = "products" if "Product" in ui_name else "orders" if "Order" in ui_name else default_var
            if disp_var not in var_paths:
                disp_var = default_var
            lines.append(f"  <div v-if=\"path === '{pkey}'\" class=\"dashboard\">")
            lines.append(f"    <h1>{ui_name}</h1>")
            lines.append(f"    <pre>{{{{ JSON.stringify({disp_var}, null, 2) }}}}</pre>")
            lines.append("  </div>")
        lines.append("</template>")
        return "\n".join(lines)

    def emit_svelte_browser(self, ir: Dict[str, Any]) -> str:
        """Emit Svelte single-file app; hash router, fetch API."""
        fe = ir["services"].get("fe", {})
        uis = fe.get("ui", {})
        routes = fe.get("routes", [])
        path_to_var = self._path_to_var(ir)
        api_base = "/" + ((ir["services"].get("core", {}).get("path") or "/api").strip("/") or "api")
        route_map = {r["path"]: r["ui"] for r in routes} if routes else {"/": next(iter(uis.keys()), "Dashboard")}
        var_paths = {v: (p, m) for (p, m), v in path_to_var.items()}
        lines = [
            "<script>",
            "  import { onMount } from 'svelte';",
            "  let path = typeof location !== 'undefined' ? (location.hash || '#/').slice(1) || '/' : '/';",
            "  const R = " + json.dumps(route_map),
        ]
        for var, (p, m) in var_paths.items():
            lines.append(f"  let {var} = [];")
        lines.append("  onMount(() => {")
        for var, (p, m) in var_paths.items():
            meth = self._http_method_upper(m or "G")
            lines.append(f"    fetch('{api_base}{p}', {{ method: '{meth}' }}).then(r => r.json()).then(d => {{ {var} = d.data || [] }});")
        lines.append("  });")
        lines.append("</script>")
        lines.append("<svelte:window on:hashchange={() => path = (location.hash || '#/').slice(1) || '/'} />")
        lines.append("<nav>{#each Object.keys(R) as p}<a href=\"#{p}\">{p}</a>{/each}</nav>")
        default_var = list(var_paths.keys())[0] if var_paths else "data"
        for pkey, ui_name in route_map.items():
            disp_var = "products" if "Product" in ui_name else "orders" if "Order" in ui_name else default_var
            if disp_var not in var_paths:
                disp_var = default_var
            lines.append(f"{{#if path === '{pkey}'}}<div class=\"dashboard\"><h1>{ui_name}</h1><pre>{{JSON.stringify({disp_var}, null, 2)}}</pre></div>{{/if}}")
        return "\n".join(lines)

    def emit_sql_migrations(self, ir: Dict[str, Any], dialect: str = "postgres") -> str:
        """Emit SQL migrations from D types. dialect: postgres | mysql."""
        def sql_type(t: str) -> str:
            t = (t or "").strip()
            if t in ("I", "i"):
                return "INTEGER"
            if t in ("S", "s", "B"):
                return "VARCHAR(255)" if dialect == "postgres" else "VARCHAR(255)"
            if t == "F":
                return "DOUBLE PRECISION" if dialect == "postgres" else "DOUBLE"
            if t in ("D", "J"):
                return "TIMESTAMP" if t == "D" else "JSONB" if dialect == "postgres" else "JSON"
            if t.startswith("E["):
                return "VARCHAR(100)"
            if t.startswith("A["):
                return "JSONB" if dialect == "postgres" else "JSON"
            return "VARCHAR(255)"
        lines = ["-- AINL SQL migration from D types", f"-- dialect: {dialect}", ""]
        for name, data in ir.get("types", {}).items():
            fields = data.get("fields", {})
            cols = []
            if "id" not in fields:
                cols.append("id SERIAL PRIMARY KEY" if dialect == "postgres" else "id INT AUTO_INCREMENT PRIMARY KEY")
            for f, t in fields.items():
                cols.append(f"  {f} {sql_type(t)}")
            cols_str = ",\n".join(cols)
            lines.append(f"CREATE TABLE IF NOT EXISTS {name} (\n{cols_str}\n);")
            lines.append("")
        for name, data in ir.get("types", {}).items():
            for rel in data.get("relations", []):
                fk = rel.get("fk")
                target = rel.get("target")
                if fk and target:
                    cname = f"fk_{name}_{fk}"
                    lines.append(f"ALTER TABLE {name} ADD CONSTRAINT {cname} FOREIGN KEY ({fk}) REFERENCES {target}(id);")
            for idx_fields in data.get("indexes", []):
                if idx_fields:
                    idx_name = f"idx_{name}_{'_'.join(idx_fields)}"
                    lines.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {name} ({', '.join(idx_fields)});")
            if data.get("relations") or data.get("indexes"):
                lines.append("")
        return "\n".join(lines)

    def emit_env_example(self, ir: Dict[str, Any]) -> str:
        """Emit .env.example and config notes from config.env, S, C, P."""
        lines = ["# AINL emitted env (copy to .env)", ""]
        for e in ir.get("config", {}).get("env", []):
            req = "required" if e.get("required") else "optional"
            default = f"  # default: {e.get('default')}" if e.get("default") else ""
            lines.append(f"{e.get('name')}={default}  # {req}")
        core = ir.get("services", {}).get("core", {})
        if core:
            lines.append("# API base (from S core path)")
        lines.append("DATABASE_URL=postgresql://user:pass@localhost:5432/dbname")
        for name, defn in ir.get("services", {}).get("cache", {}).get("defs", {}).items():
            lines.append(f"CACHE_{name.upper()}_KEY=")
            lines.append(f"CACHE_{name.upper()}_TTL={defn.get('ttl', '3600')}")
        for name, defn in ir.get("services", {}).get("pay", {}).get("defs", {}).items():
            lines.append(f"STRIPE_SECRET_KEY=sk_...  # for P {name}")
        if ir.get("services", {}).get("auth"):
            auth = ir["services"]["auth"]
            lines.append(f"AUTH_{auth.get('kind', 'jwt').upper()}_SECRET=  # from A {auth.get('arg', '')}")
        lines.append("BACKEND_URL=http://localhost:8765  # for Next.js / proxy")
        return "\n".join(lines)

    def emit_health_readiness(self, ir: Dict[str, Any]) -> str:
        """Emit Python snippet to add /health and /ready to FastAPI app."""
        return '''
@api.get("/health")
def health():
    return {"status": "ok"}

@api.get("/ready")
def ready():
    return {"ready": True}
'''

    def emit_runbooks(self, ir: Dict[str, Any]) -> str:
        """Emit runbooks.md from Run ops."""
        lines = ["# Runbooks", ""]
        for name, steps in ir.get("runbooks", {}).items():
            lines.append(f"## {name}")
            lines.append("")
            for i, step in enumerate(steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        return "\n".join(lines) if ir.get("runbooks") else "# Runbooks\n\n(No runbooks defined.)\n"

    def emit_rag_pipeline(self, ir: Dict[str, Any]) -> str:
        """Emit Python RAG pipeline: individual pieces (chunk, embed, index, retrieve, augment, generate) + full pipeline from rag.Pipe."""
        r = ir.get("rag", {})
        if not r:
            return "# AINL RAG emit\n# No rag.* ops in spec.\n"
        lines = [
            "# AINL RAG pipeline (from rag.* ops)",
            "# Use: ingest (chunk+embed+index), retrieve, or run_pipeline(name).",
            "import os",
            "from typing import List, Dict, Any, Optional",
            "",
            "def _chunk_text(text: str, strategy: str, size: int, overlap: int) -> List[str]:",
            "    if strategy == 'fixed':",
            "        return [text[i:i+size] for i in range(0, len(text), max(1, size - overlap))]",
            "    return [text[i:i+size] for i in range(0, len(text), size)]",
            "",
            "def _embed(model: str, texts: List[str], dim: Optional[int] = None) -> List[List[float]]:",
            "    # Stub: use sentence-transformers or OpenAI; require RAG_EMBED_MODEL env",
            "    return [[0.0] * (dim or 384) for _ in texts]",
            "",
            "def _store_add(store_type: str, name: str, ids: List[str], vectors: List[List[float]], meta: Optional[List[Dict]] = None) -> None:",
            "    pass  # Stub: pgvector, qdrant, or in-memory",
            "",
            "def ingest_source(source_name: str, cfg: Dict) -> None:",
            "    src_type, path = cfg.get('type'), cfg.get('path', '')",
            "    text = ''  # Stub: read file/url/db by path",
            "    print(f'Ingest {source_name}: {src_type} {path}')",
            "",
            "def retrieve(retriever_name: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:",
            "    # Stub: lookup rag.retrievers[retriever_name], embed query, search store, return chunks",
            "    return [{'text': '', 'score': 0.0}] * top_k",
            "",
            "def augment(aug_name: str, chunks: List[Dict], query: str) -> str:",
            "    cfg = _rag.get('augment', {}).get(aug_name, {})",
            "    tpl = cfg.get('tpl', 'query: {query}\\nchunks: {chunks}')",
            "    return tpl.replace('{query}', query).replace('{chunks}', str(chunks))",
            "",
            "def generate(gen_name: str, prompt: str) -> str:",
            "    cfg = _rag.get('generate', {}).get(gen_name, {})",
            "    model = cfg.get('model', '')",
            "    # Stub: call LLM (OpenAI, local); require RAG_LLM_MODEL or similar",
            "    return ''",
            "",
            "def run_pipeline(pipe_name: str, query: str) -> str:",
            "    p = _rag.get('pipelines', {}).get(pipe_name, {})",
            "    ret_name = p.get('ret')",
            "    aug_name = p.get('aug')",
            "    gen_name = p.get('gen')",
            "    if not ret_name: return ''",
            "    ret_cfg = _rag.get('retrievers', {}).get(ret_name, {})",
            "    top_k = int(ret_cfg.get('top_k', 5))",
            "    chunks = retrieve(ret_name, query, top_k)",
            "    prompt = augment(aug_name, chunks, query) if aug_name else str(chunks)",
            "    return generate(gen_name, prompt) if gen_name else prompt",
            "",
            "_rag = " + json.dumps(r, indent=2),
            "",
            "if __name__ == '__main__':",
            "    import sys",
            "    pipe = list(_rag.get('pipelines', {}))[0] if _rag.get('pipelines') else None",
            "    if pipe and len(sys.argv) > 1:",
            "        print(run_pipeline(pipe, sys.argv[1]))",
            "    else:",
            "        print('RAG config:', list(_rag.keys()))",
            "",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    test_code = """
S core web /api
D User id:I em:S rl:E[Ad,Us]
E /us G ->L1
L1: R db.F User * ->us J us
S fe web /
U Db
T us:A[User]
U Tb us
"""
    compiler = AICodeCompiler()
    ir = compiler.compile(test_code)
    print("IR keys:", list(ir.keys()))
    print("labels:", ir["labels"])
    print("\n--- React ---\n", compiler.emit_react(ir))
    print("\n--- Prisma ---\n", compiler.emit_prisma_schema(ir))
    print("\n--- Python API ---\n", compiler.emit_python_api(ir))
    print("\n--- MT5 ---\n", compiler.emit_mt5(ir))
    print("\n--- Scraper ---\n", compiler.emit_python_scraper(ir))
