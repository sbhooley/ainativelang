"""
AINL 1.0 — Ultra-compact compiler.
Syntax: 1-char OP + slots (space-delimited; quoted strings preserved). Parses to IR for React/TS/Python/MT5/Scraper emission.
Spec: docs/AINL_SPEC.md. Canonical IR: labels[id].nodes/edges + legacy.steps.
Lossless: source stored exactly; tokenizer emits Token(kind, raw, value, span); meta keeps raw_line + token spans.
"""
import copy
import json
import re
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Sequence

from compiler_diagnostics import (
    CompilationDiagnosticError,
    CompilerContext,
    Diagnostic,
    make_diagnostic,
)

from tooling.graph_normalize import (
    DEFAULT_PORTS,
    VALID_PORTS as GRAPH_VALID_PORTS,
    normalize_labels,
)
from tooling.emit_targets import FULL_EMIT_TARGET_ORDER
from tooling.effect_analysis import (
    ADAPTER_EFFECT,
    annotate_labels_effect_analysis,
    dataflow_defined_before_use,
    propagate_inter_label_entry_defs,
    strict_adapter_is_allowed,
    strict_adapter_key_for_step,
)
from tooling.emission_planner import apply_minimal_emit_python_api_stub_fallback
from tooling.ir_canonical import attach_label_and_node_hashes, graph_semantic_checksum

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


# Module ops: unprefixed aliases → canonical module.op; prefixed (ops.Env, fe.Tok) stay as-is.
# Tokenizer keeps "module.op" as one bare token (no split on '.'); both forms normalize in IR.
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
    "Pol": {"scope": "top", "min_slots": 1},
    "Txn": {"scope": "top", "min_slots": 1},
    "Inc": {"scope": "top", "min_slots": 1},
    "include": {"scope": "top", "min_slots": 1},
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
    "X": {"scope": "label", "min_slots": 2},
    "Loop": {"scope": "label", "min_slots": 4},
    "While": {"scope": "label", "min_slots": 3},
    # Capability runtime steps
    "CacheGet": {"scope": "label", "min_slots": 2},
    "CacheSet": {"scope": "label", "min_slots": 3},
    "QueuePut": {"scope": "label", "min_slots": 2},
    "Tx": {"scope": "label", "min_slots": 2},
    "Enf": {"scope": "label", "min_slots": 1},
}

# Compiler-owned grammar metadata used by prefix-constrained decoding.
# This is declarative shape metadata (not full semantic validation logic).
GRAMMAR_CLASS_NEWLINE = "NEWLINE"
GRAMMAR_CLASS_QUOTE_CLOSE = "QUOTE_CLOSE"
GRAMMAR_CLASS_ARROW_CONT = "ARROW_CONT"
GRAMMAR_CLASS_LABEL_ARROW_CONT = "LABEL_ARROW_CONT"
GRAMMAR_CLASS_LABEL_DECL = "LABEL_DECL"
GRAMMAR_CLASS_MODULE_OP = "MODULE_OP"
GRAMMAR_CLASS_LINE_STARTER = "LINE_STARTER"
GRAMMAR_CLASS_GENERIC = "GENERIC"

OP_GRAMMAR: Dict[str, Dict[str, Any]] = {
    "E": {
        "slots": [
            {"name": "path", "class": "PATH", "required": True},
            {"name": "method", "class": "METHOD", "required": True},
            {"name": "label", "class": "LABEL_REF", "required": True},
            {"name": "out", "class": "OUT_VAR", "required": False},
            {"name": "return_type", "class": "TYPE_REF", "required": False},
            {"name": "description", "class": "DESC_TOKEN", "required": False},
        ]
    },
    "If": {
        "slots": [
            {"name": "cond", "class": "COND", "required": True},
            {"name": "then", "class": "LABEL_REF", "required": True},
            {"name": "else", "class": "LABEL_REF", "required": False},
        ]
    },
    "R": {
        "slots": [
            {"name": "adapter", "class": "ADAPTER_OP", "required": True},
            {"name": "target", "class": "TARGET", "required": True},
            {"name": "arg", "class": "FREE_ARG", "required": False, "repeat": True},
            {"name": "out", "class": "OUT_VAR", "required": False},
        ]
    },
    "Call": {
        "slots": [
            {"name": "label", "class": "LABEL_REF", "required": True},
            {"name": "out", "class": "OUT_VAR", "required": False},
        ]
    },
    "S": {
        "slots": [
            {"name": "service_name", "class": "SERVICE_NAME", "required": True},
            {"name": "service_mode", "class": "SERVICE_MODE", "required": True},
            {"name": "service_path", "class": "PATH", "required": False},
        ]
    },
    "D": {
        "slots": [
            {"name": "entity", "class": "ENTITY_NAME", "required": True},
            {"name": "field", "class": "FIELD_TYPE", "required": False, "repeat": True},
        ]
    },
    "J": {
        "slots": [
            {"name": "var", "class": "VAR_NAME", "required": False},
        ]
    },
    "U": {
        "slots": [
            {"name": "ui", "class": "UI_NAME", "required": True},
            {"name": "prop", "class": "VAR_NAME", "required": False, "repeat": True},
        ]
    },
}


def grammar_is_identifier(tok: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tok or ""))


def grammar_is_label_decl(tok: str) -> bool:
    return bool(re.match(r"^L\d+:$", tok or ""))


def grammar_is_label_ref(tok: str) -> bool:
    if not tok or tok.endswith(":"):
        return False
    if tok.startswith("->L") and tok[3:].isdigit():
        return True
    return bool(tok.startswith("L") and tok[1:].isdigit())


def grammar_is_out_var(tok: str) -> bool:
    return bool(tok and tok.startswith("->") and not tok.startswith("->L") and len(tok) > 2)


def grammar_is_type_ref(tok: str) -> bool:
    if tok in {"I", "i", "F", "S", "s", "B", "D", "J"}:
        return True
    if tok.startswith("A[") and tok.endswith("]"):
        return True
    if tok.startswith("E[") and tok.endswith("]"):
        return True
    return bool(re.match(r"^[A-Z][A-Za-z0-9_]*$", tok or ""))


def grammar_is_field_type(tok: str) -> bool:
    if ":" not in (tok or ""):
        return False
    name, typ = tok.split(":", 1)
    if not grammar_is_identifier(name):
        return False
    if typ.endswith("?") or typ.endswith("!"):
        typ = typ[:-1]
    return grammar_is_type_ref(typ)


def grammar_matches_token_class(token_class: str, tok: str) -> bool:
    if token_class == "LABEL_REF":
        return grammar_is_label_ref(tok)
    if token_class == "OUT_VAR":
        return grammar_is_out_var(tok)
    if token_class == "PATH":
        return bool(tok and tok.startswith("/"))
    if token_class == "METHOD":
        return tok in {"G", "P", "U", "D"}
    if token_class == "FIELD_TYPE":
        return grammar_is_field_type(tok)
    if token_class in {"VAR_NAME", "ENTITY_NAME", "UI_NAME", "SERVICE_NAME", "IDENT"}:
        return grammar_is_identifier(tok)
    if token_class == "TYPE_REF":
        return grammar_is_type_ref(tok)
    if token_class == "ADAPTER_OP":
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$", tok or ""))
    if token_class == "TARGET":
        return tok == "*" or grammar_is_identifier(tok) or (tok or "").startswith("/")
    if token_class == "FREE_ARG":
        return bool(tok) and not tok.isspace()
    if token_class == "DESC_TOKEN":
        return bool(tok) and not tok.startswith("->")
    if token_class == "COND":
        return bool(tok) and not tok.startswith("->")
    return False


def grammar_next_slot_classes(op: str, slots_so_far: List[str]) -> Set[str]:
    """
    Compiler-owned slot transition helper for prefix decoding.
    Returns token classes admissible for the *next token* for a given op.
    """
    schema = list(OP_GRAMMAR.get(op, {}).get("slots", []))
    if not schema:
        return set()

    # Position-dependent handling that cannot be expressed by simple required/repeat flags.
    if op == "R":
        if len(slots_so_far) == 0:
            return {"ADAPTER_OP"}
        if len(slots_so_far) == 1:
            return {"TARGET"}
        if slots_so_far and slots_so_far[-1].startswith("->"):
            return set()
        return {"FREE_ARG", "OUT_VAR"}

    if op == "E":
        if len(slots_so_far) == 0:
            return {"PATH"}
        if len(slots_so_far) == 1:
            return {"METHOD"}
        if len(slots_so_far) == 2:
            return {"LABEL_REF"}
        if len(slots_so_far) == 3:
            return {"OUT_VAR", "TYPE_REF", "DESC_TOKEN"}
        if len(slots_so_far) == 4:
            if grammar_is_out_var(slots_so_far[3]):
                return {"TYPE_REF", "DESC_TOKEN"}
            if grammar_is_type_ref(slots_so_far[3]):
                return {"DESC_TOKEN"}
            return set()
        return set()

    idx = len(slots_so_far)
    if idx >= len(schema):
        return set()
    cur = schema[idx]
    out = {str(cur.get("class"))}
    if not bool(cur.get("required", True)) and idx + 1 < len(schema):
        out.add(str(schema[idx + 1].get("class")))
    if bool(cur.get("repeat", False)) and idx + 1 < len(schema):
        out.add(str(schema[idx + 1].get("class")))
    return out


def grammar_prefix_line_ok(op: str, slots: List[str], is_last_partial: bool) -> bool:
    """
    Compiler-owned semantic-prefix viability checks for individual ops.
    """
    def _is_at_node(tok: str) -> bool:
        if not tok:
            return False
        s = tok[1:] if tok.startswith("@") else tok
        return bool(re.match(r"^n\d+$", s))

    if op == "E":
        if len(slots) >= 3 and not grammar_is_label_ref(slots[2]):
            if not (is_last_partial and (slots[2] in {"-", "->"} or slots[2].startswith("->L"))):
                return False
        if len(slots) >= 4 and slots[3].startswith("->") and not grammar_is_out_var(slots[3]):
            return False
        if len(slots) >= 5 and not grammar_is_type_ref(slots[4]):
            return False if not is_last_partial else True
    if op == "If":
        if len(slots) >= 2 and not grammar_is_label_ref(slots[1]):
            if not (is_last_partial and (slots[1] in {"-", "->"} or slots[1].startswith("->L"))):
                return False
        if len(slots) >= 3 and not grammar_is_label_ref(slots[2]):
            if not (is_last_partial and (slots[2] in {"-", "->"} or slots[2].startswith("->L"))):
                return False
    if op == "Call":
        if len(slots) >= 1 and not grammar_is_label_ref(slots[0]):
            if not (is_last_partial and slots[0].startswith("L")):
                return False
        if len(slots) >= 2 and not grammar_is_out_var(slots[1]):
            if not (is_last_partial and slots[1] in {"-", "->"}):
                return False
    if op == "Err":
        if len(slots) >= 1 and _is_at_node(slots[0]) and len(slots) < 2:
            return False if not is_last_partial else True
        if len(slots) >= 2 and _is_at_node(slots[0]) and not grammar_is_label_ref(slots[1]):
            return False if not is_last_partial else True
    if op == "R" and slots and slots[-1].startswith("->") and not grammar_is_out_var(slots[-1]):
        return False if not is_last_partial else True
    return True


def grammar_scan_lexical_prefix_state(prefix: str, tokenizer: Optional["AICodeCompiler"] = None) -> Dict[str, Any]:
    """
    Compiler-owned incremental lexical scanner for the current line.
    Returns a plain dict to keep import boundaries lightweight.
    """
    comp = tokenizer or AICodeCompiler()
    line = prefix[prefix.rfind("\n") + 1 :] if prefix else ""
    tokens: List[str] = []
    cur: List[str] = []
    in_quote = False
    in_comment = False
    escaped = False
    for ch in line:
        if in_comment:
            break
        if in_quote:
            cur.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_quote = False
                cur = []
            continue
        if ch == "#":
            if cur:
                tokens.append("".join(cur))
                cur = []
            in_comment = True
            continue
        if ch.isspace():
            if cur:
                tokens.append("".join(cur))
                cur = []
            continue
        if ch == '"':
            if cur:
                tokens.append("".join(cur))
                cur = []
            in_quote = True
            cur.append(ch)
            escaped = False
            continue
        cur.append(ch)
    token_in_progress = ""
    if in_quote:
        token_in_progress = "".join(cur)
    elif not in_comment and cur:
        token_in_progress = "".join(cur)
        tokens.append(token_in_progress)

    if not in_quote:
        try:
            toks = comp.tokenize_line_lossless(line, 1)
            tokens = [t["value"] for t in toks if t.get("kind") in ("bare", "string")]
        except Exception:
            pass

    return {
        "line": line,
        "in_quote": in_quote,
        "in_comment": in_comment,
        "ends_with_whitespace": bool(line) and line[-1].isspace(),
        "token_in_progress": token_in_progress,
        "tokens": tokens,
    }


def grammar_apply_candidate_to_prefix(prefix: str, cand: str, tokenizer: Optional["AICodeCompiler"] = None) -> str:
    """
    Compiler-owned prefix edit transition used by constrained decoding.
    """
    lex = grammar_scan_lexical_prefix_state(prefix, tokenizer=tokenizer)
    if cand == "\n":
        return prefix + "\n"
    if bool(lex.get("in_quote")):
        return prefix + cand

    last = str(lex.get("line", ""))
    head = prefix[: len(prefix) - len(last)]
    token_in_progress = str(lex.get("token_in_progress", ""))
    ends_with_whitespace = bool(lex.get("ends_with_whitespace"))
    in_comment = bool(lex.get("in_comment"))

    if token_in_progress and not ends_with_whitespace and not in_comment:
        if token_in_progress in {"-", "->"}:
            return prefix + cand
        if token_in_progress == "->L":
            if cand.startswith("->L"):
                return prefix + cand[3:]
            return prefix + cand
        if cand.startswith(token_in_progress):
            return head + last[: len(last) - len(token_in_progress)] + cand
        return prefix + " " + cand

    if not last or last.endswith((" ", "\t")):
        return prefix + cand
    return prefix + " " + cand


def grammar_active_label_scope(prefix: str, tokenizer: Optional["AICodeCompiler"] = None) -> bool:
    """
    Compiler-owned active-label-scope computation for prefix state.
    """
    comp = tokenizer or AICodeCompiler()
    in_label = False
    lines = (prefix or "").split("\n")
    last_partial = not (prefix or "").endswith("\n")

    for i, raw in enumerate(lines):
        if not raw.strip():
            continue
        is_last = i == len(lines) - 1
        try:
            toks = comp.tokenize_line_lossless(raw, i + 1)
            node = comp.parse_line_lossless(toks, raw, i + 1)
        except ValueError:
            if is_last and last_partial:
                break
            return in_label

        op_value = node.get("op_value", "")
        if not op_value:
            continue
        if grammar_is_label_decl(op_value):
            in_label = True
            continue

        op = MODULE_ALIASES.get(op_value, op_value)
        scope = OP_REGISTRY.get(op, {}).get("scope", "top")
        if in_label and op not in comp.STEP_OPS and scope not in ("label", "any"):
            in_label = False

    return in_label


def runtime_normalize_label_id(token: Any) -> str:
    """
    Compiler-owned runtime label normalization.
    Accepted forms: ->L1, L1, 1, L1:suffix, ->anything.
    Returns canonical numeric/id payload used as labels[] key.
    """
    s = str(token or "").strip()
    if s.startswith("->L"):
        s = s[3:]
    elif s.startswith("->"):
        s = s[2:]
    elif s.startswith("L"):
        s = s[1:]
    if ":" in s:
        # Historical/runtime compatibility: "L1:entry" should normalize to "1".
        s = s.split(":", 1)[0]
    return s


def runtime_normalize_node_id(token: Any) -> Optional[str]:
    """
    Compiler-owned runtime node-id normalization.
    Accepted forms: @n3, n3; returns canonical n<number> or None.
    """
    if not isinstance(token, str):
        return None
    s = token.strip()
    if s.startswith("@"):
        s = s[1:]
    if not s.startswith("n"):
        return None
    rest = s[1:]
    if not rest.isdigit():
        return None
    return "n" + str(int(rest))


def runtime_canonicalize_r_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compiler-owned canonical R-step view for runtime execution.

    Canonical fields:
    - adapter: adapter or adapter.verb (required for canonical dispatch)
    - target: route/entity/operation target
    - args: positional request args (resolved at runtime)
    - out: destination variable (default res)

    Backward-compat source fields (src/req_op/entity/fields) are folded into
    canonical fields when adapter/target/args are missing.
    """
    adapter = step.get("adapter", "")
    if not adapter:
        src = (step.get("src") or "").strip()
        req_op = (step.get("req_op") or "").strip()
        adapter = f"{src}.{req_op}" if src and req_op else src

    target = step.get("target", "")
    if not target:
        target = step.get("entity", "")

    args = list(step.get("args") or [])
    # Legacy-only folding: compiler-emitted canonical R steps may still carry
    # compatibility "fields" metadata (often "*"), which must NOT be promoted
    # into args when canonical adapter/target are already present.
    if not args and not step.get("adapter") and step.get("fields") not in (None, ""):
        args = [step.get("fields")]

    out = step.get("out", "res")
    return {"adapter": adapter, "target": target, "args": args, "out": out}


def grammar_prefix_completable(prefix: str, tokenizer: Optional["AICodeCompiler"] = None) -> bool:
    """
    Compiler-owned prefix viability check for formal constrained decoding.
    """
    comp = tokenizer or AICodeCompiler()
    lines = (prefix or "").split("\n")
    last_partial = not (prefix or "").endswith("\n")
    in_label_scope = False

    for i, raw in enumerate(lines):
        is_last = i == len(lines) - 1
        if not raw.strip():
            continue
        try:
            toks = comp.tokenize_line_lossless(raw, i + 1)
            node = comp.parse_line_lossless(toks, raw, i + 1)
        except ValueError:
            return bool(is_last and last_partial)

        op_value = node.get("op_value", "")
        slots = node.get("slot_values", [])
        if not op_value and not slots:
            continue
        if grammar_is_label_decl(op_value):
            in_label_scope = True
            continue

        op = MODULE_ALIASES.get(op_value, op_value)
        spec = OP_REGISTRY.get(op)
        if spec is None:
            return bool(is_last and last_partial)

        scope = spec.get("scope", "top")
        min_slots = int(spec.get("min_slots", 0))

        if in_label_scope and op not in comp.STEP_OPS and scope not in ("label", "any"):
            in_label_scope = False

        if not (is_last and last_partial):
            if scope == "label" and not in_label_scope:
                return False
            if scope == "top" and in_label_scope:
                return False
            if len(slots) < min_slots:
                return False

        if not grammar_prefix_line_ok(op, slots, is_last and last_partial):
            return False

        if in_label_scope and op not in comp.STEP_OPS:
            in_label_scope = False

    return True


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
        self._label_decl_lines: Dict[str, int] = {}
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
        self.capabilities: Dict[str, Any] = {"auth": {}, "policy": {}, "cache": {}, "queue": {}, "txn": {}}
        self._warnings: List[str] = []

    def _augment_errors_with_suggestions(self):
        """Add suggestion hints to error messages for common mistakes."""
        from tooling.effect_analysis import ADAPTER_EFFECT
        # Known modules for which adapter.verb pairs exist
        known_keys = set(ADAPTER_EFFECT.keys()) if ADAPTER_EFFECT else set()
        # Known top-level modules
        known_modules = {
            "core",
            "cache",
            "http",
            "https",
            "bridge",
            "sqlite",
            "fs",
            "email",
            "calendar",
            "social",
            "db",
            "queue",
            "svc",
            "wasm",
        }

        new_errors = []
        for err in self._errors:
            suggestion = None
            # Case: unknown adapter.verb (e.g., 'http.Unknown')
            if "unknown adapter.verb" in err:
                m = re.search(r"adapter\.verb (.+?) (?:in|$)", err)
                if m:
                    unknown = m.group(1)
                    close = difflib.get_close_matches(unknown, known_keys, n=1, cutoff=0.6)
                    if close:
                        suggestion = f"Did you mean '{close[0]}'?"
            # Case: unknown module (e.g., 'htp' not found)
            if "unknown module" in err:
                m = re.search(r"unknown module (.+?) in", err)
                if m:
                    unknown_mod = m.group(1)
                    close_mod = difflib.get_close_matches(unknown_mod, known_modules, n=3, cutoff=0.5)
                    if close_mod:
                        suggestion = f"Known modules: {', '.join(sorted(close_mod))}"
            # Case: If then target must be ->L<n>
            if "If then target must be" in err:
                suggestion = "Use conditional jump: ->L<number> or L<number>"
            # Case: Label graph node ids must be contiguous n1..nK
            if "graph node ids must be contiguous" in err:
                suggestion = "Ensure node IDs are exactly n1, n2, n3... without gaps"
            # Case: unknown op in meta (lossless)
            if "unknown op" in err.lower():
                suggestion = "Check op name spelling; valid ops: X, R, L, J, If, Loop, While, Err, CacheGet, CacheSet, etc."

            if suggestion:
                err = f"{err} Suggestion: {suggestion}"
            new_errors.append(err)

        self._errors = new_errors

    _DIAG_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)
    _DIAG_LABEL_NODE_RE = re.compile(r"Label\s+'([^']+)':\s+node\s+'([^']+)'", re.IGNORECASE)
    _DIAG_OP_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*):")

    def _diag_line_from_message(self, message: str) -> Optional[int]:
        m = self._DIAG_LINE_RE.search(message or "")
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _strict_op_token_char_span(
        self,
        line_node: Dict[str, Any],
        lineno: int,
        source_lines: Sequence[str],
    ) -> Tuple[Optional[Tuple[int, int]], int]:
        """Absolute (start, end) char span of the line op token and 1-based col_offset.

        Used for Phase 2 structured diagnostics; returns (None, 1) if token span is missing.
        """
        op_value = line_node.get("op_value")
        op_col_start_0 = 0
        op_col_end_0 = 1
        found = False
        for tok in line_node.get("tokens", []):
            sp = tok.get("span") or {}
            if sp.get("line") == lineno and tok.get("value") == op_value:
                op_col_start_0 = int(sp.get("col_start", 0))
                op_col_end_0 = int(sp.get("col_end", op_col_start_0 + 1))
                found = True
                break
        if not found or lineno < 1:
            return None, 1
        line_start = sum(len(source_lines[i]) + 1 for i in range(lineno - 1))
        return (line_start + op_col_start_0, line_start + op_col_end_0), op_col_start_0 + 1

    def _strict_nth_slot_content_char_span(
        self,
        line_node: Dict[str, Any],
        slot_index: int,
        lineno: int,
        source_lines: Sequence[str],
    ) -> Tuple[Optional[Tuple[int, int]], int]:
        """Absolute span for argument slot slot_index (0 = first slot after op). Fallback: op token."""
        content = [t for t in line_node.get("tokens", []) if t.get("kind") in ("bare", "string")]
        tok_idx = 1 + int(slot_index)
        if len(content) <= tok_idx:
            return self._strict_op_token_char_span(line_node, lineno, source_lines)
        tok = content[tok_idx]
        sp = tok.get("span") or {}
        if int(sp.get("line") or 0) != lineno:
            return self._strict_op_token_char_span(line_node, lineno, source_lines)
        c0 = int(sp.get("col_start", 0))
        c1 = int(sp.get("col_end", c0 + 1))
        line_start = sum(len(source_lines[i]) + 1 for i in range(lineno - 1))
        return (line_start + c0, line_start + c1), c0 + 1

    def _strict_closest_label_id(self, missing: str) -> Optional[str]:
        """Best-effort label id suggestion using declared labels (strict / IR).

        Uses difflib (cutoff 0.6) first; for all-digit ids, falls back to the nearest
        declared numeric label within a small distance (adjacent ids like 41 vs 40
        score ~0.5 in difflib and would otherwise miss at 0.6).
        """
        ms = str(missing)
        candidates = sorted(str(k) for k in self.labels.keys() if str(k) != "_anon")
        if not candidates:
            return None
        matches = difflib.get_close_matches(ms, candidates, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        if ms.isdigit():
            numeric: List[Tuple[int, str]] = []
            for c in candidates:
                if str(c).isdigit():
                    numeric.append((abs(int(ms) - int(c)), str(c)))
            if numeric:
                dist, c = min(numeric, key=lambda t: t[0])
                if dist <= max(2, len(ms)):
                    return c
        return None  # No close match — callers omit "Did you mean" from suggested_fix.

    def _strict_label_decl_line_char_span(
        self,
        label_id: Optional[str],
        cst_lines: Sequence[Dict[str, Any]],
        source_lines: Sequence[str],
    ) -> Optional[Tuple[int, int]]:
        """Char span of the declaration op token for L<label_id>: (first match in CST)."""
        if not label_id:
            return None
        want = str(label_id)
        for ln in cst_lines:
            if not isinstance(ln, dict):
                continue
            opv = str(ln.get("op_value") or "")
            if opv.startswith("L") and opv.endswith(":") and opv[1:-1] == want:
                lo = int(ln.get("lineno") or 1)
                span, _ = self._strict_op_token_char_span(ln, lo, source_lines)
                return span
        return None

    def _strict_endpoint_line_node(
        self,
        path: str,
        method: str,
        cst_lines: Sequence[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Lossless CST row for E path method ... matching this endpoint."""
        want_m = self._dsl_method(method)
        for ln in cst_lines:
            if not isinstance(ln, dict):
                continue
            if str(ln.get("op_value") or "").strip() != "E":
                continue
            sv = list(ln.get("slot_values") or [])
            if len(sv) < 3:
                continue
            if sv[0] != path:
                continue
            if self._dsl_method(sv[1]) != want_m:
                continue
            return ln
        return None

    def _strict_first_step_ref_lineno(self, target_id: str) -> Optional[int]:
        """Earliest source lineno of a control-flow step that references normalized label target_id."""
        tid = str(target_id)
        best: Optional[int] = None
        for _lid, body in self.labels.items():
            steps = body.get("legacy", {}).get("steps", [])
            for s in steps:
                if not isinstance(s, dict):
                    continue
                ln = s.get("lineno")
                if not isinstance(ln, int):
                    continue
                opn = s.get("op")
                hit = False
                if opn == "If":
                    for key in ("then", "else"):
                        if self._norm_lid(s.get(key)) == tid:
                            hit = True
                            break
                elif opn == "Err":
                    hit = self._norm_lid(s.get("handler")) == tid
                elif opn == "Call":
                    hit = self._norm_lid(s.get("label")) == tid
                elif opn in ("Loop", "While"):
                    for key in ("body", "after"):
                        if self._norm_lid(s.get(key)) == tid:
                            hit = True
                            break
                if hit:
                    best = ln if best is None else min(best, ln)
        return best

    def _strict_next_free_numeric_label_id(self) -> str:
        """Next unused numeric label id string for suggestions (digits only in pool)."""
        nums: List[int] = []
        for lid in set(list(self.labels.keys()) + list(self._label_decl_lines.keys())):
            s = str(lid).strip()
            if s.isdigit():
                nums.append(int(s))
        return str(max(nums) + 1) if nums else "1"

    def _resolve_include_path(
        self, raw_path: str, parent_source_path: Optional[str]
    ) -> Tuple[Optional[Path], Optional[str]]:
        """Resolve include path: parent-relative, then cwd, then cwd/modules/."""
        raw = (raw_path or "").strip()
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        raw = raw.strip()
        if not raw:
            return None, "empty include path"
        candidates: List[Path] = []
        try:
            if parent_source_path:
                p = Path(parent_source_path)
                base = p.parent if p.is_file() else p
                candidates.append((base / raw).resolve())
            candidates.append((Path.cwd() / raw).resolve())
            candidates.append((Path.cwd() / "modules" / raw).resolve())
        except (OSError, ValueError) as e:
            return None, str(e)
        seen: Set[str] = set()
        for c in candidates:
            key = str(c)
            if key in seen:
                continue
            seen.add(key)
            try:
                if c.is_file():
                    return c, None
            except OSError:
                continue
        return None, f"include path not found: {raw_path!r}"

    def _scan_include_prelude(
        self, lines: List[str]
    ) -> Tuple[List[Tuple[int, Dict[str, Any]]], Set[int]]:
        """Collect leading `include` lines; stop at first other non-empty, non-comment line."""
        collected: List[Tuple[int, Dict[str, Any]]] = []
        prelude_linenos: Set[int] = set()
        for lineno, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                tokens = self.tokenize_line_lossless(line, lineno)
            except ValueError:
                break
            ln = self.parse_line_lossless(tokens, line, lineno)
            if str(ln.get("op_value") or "").lower() != "include":
                break
            collected.append((lineno, ln))
            prelude_linenos.add(lineno)
        return collected, prelude_linenos

    @staticmethod
    def _parse_include_directive(slot_values: List[str]) -> Optional[Tuple[str, str]]:
        """Return (path, alias) or None. Alias defaults to path stem."""
        if not slot_values:
            return None
        path_tok = slot_values[0]
        if len(slot_values) >= 3 and str(slot_values[1]).lower() == "as":
            alias = str(slot_values[2]).strip()
            if not alias:
                return None
        elif len(slot_values) == 1:
            alias = Path(path_tok).stem
        else:
            return None
        return path_tok, alias

    @staticmethod
    def _subgraph_source_has_top_level_e_or_s(sub_code: str) -> bool:
        """True if any non-comment line starts with top-level E or S (forbidden in strict includes)."""
        for line in sub_code.split("\n"):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            toks = s.split(None, 1)
            if not toks:
                continue
            if toks[0] in ("E", "S"):
                return True
        return False

    def _subgraph_contract_errors(self, labels: Dict[str, Any]) -> List[str]:
        """Strict include contract: exactly one ENTRY label, ≥1 EXIT_* label."""
        errs: List[str] = []
        keys = [str(k) for k in labels.keys() if str(k) != "_anon"]
        entry_keys = [k for k in keys if k == "ENTRY" or self._norm_lid(k) == "ENTRY"]
        if len(entry_keys) != 1:
            errs.append(
                f"included subgraph must have exactly one ENTRY label (found {len(entry_keys)})"
            )
        exit_keys = [k for k in keys if str(k).startswith("EXIT_")]
        if not exit_keys:
            errs.append("included subgraph must declare at least one EXIT_* label")
        return errs

    def _map_subgraph_label_ref(
        self, val: Any, labels: Dict[str, Any], idmap: Dict[str, str]
    ) -> Any:
        if val is None:
            return None
        nv = self._norm_lid(val)
        if nv is None:
            return val
        for lk in labels.keys():
            sk = str(lk)
            if self._norm_lid(sk) == nv:
                return idmap[sk]
        return val

    def _prefix_subgraph_labels(self, labels: Dict[str, Any], alias: str) -> Dict[str, Any]:
        """Deep-copy labels and prefix label keys, node ids, edges, legacy label refs."""

        def _pfx_nid(tok: Any) -> Any:
            if tok is None or not isinstance(tok, str) or not tok:
                return tok
            if tok.startswith(f"{alias}/"):
                return tok
            return f"{alias}/{tok}"

        idmap: Dict[str, str] = {}
        for lk in labels.keys():
            sk = str(lk)
            idmap[sk] = f"{alias}/{sk}"
        out: Dict[str, Any] = {}
        for lk, body in labels.items():
            sk = str(lk)
            new_lid = idmap[sk]
            body_copy = copy.deepcopy(body) if isinstance(body, dict) else body
            if not isinstance(body_copy, dict):
                out[new_lid] = body_copy
                continue
            nodes = body_copy.get("nodes")
            if isinstance(nodes, list):
                for n in nodes:
                    if isinstance(n, dict) and n.get("id") is not None:
                        oid = str(n["id"])
                        n["id"] = _pfx_nid(oid)
            edges = body_copy.get("edges")
            if isinstance(edges, list):
                for e in edges:
                    if not isinstance(e, dict):
                        continue
                    fk = e.get("from")
                    if isinstance(fk, str) and fk:
                        e["from"] = _pfx_nid(fk)
                    tk = e.get("to")
                    if e.get("to_kind") == "node" and isinstance(tk, str) and tk:
                        e["to"] = _pfx_nid(tk)
                    elif e.get("to_kind") == "label" and tk is not None:
                        mapped = self._map_subgraph_label_ref(tk, labels, idmap)
                        e["to"] = mapped
            ent = body_copy.get("entry")
            if isinstance(ent, str) and ent:
                body_copy["entry"] = _pfx_nid(ent)
            ex = body_copy.get("exits")
            if isinstance(ex, list):
                body_copy["exits"] = [_pfx_nid(x) if isinstance(x, str) else x for x in ex]
            leg = body_copy.get("legacy")
            if isinstance(leg, dict):
                steps = leg.get("steps")
                if isinstance(steps, list):
                    for s in steps:
                        if not isinstance(s, dict):
                            continue
                        opn = s.get("op")
                        if opn == "If":
                            if "then" in s:
                                s["then"] = self._map_subgraph_label_ref(s.get("then"), labels, idmap)
                            if "else" in s:
                                s["else"] = self._map_subgraph_label_ref(s.get("else"), labels, idmap)
                        elif opn == "Err" and "handler" in s:
                            s["handler"] = self._map_subgraph_label_ref(s.get("handler"), labels, idmap)
                        elif opn == "Call" and "label" in s:
                            s["label"] = self._map_subgraph_label_ref(s.get("label"), labels, idmap)
                        elif opn in ("Loop", "While"):
                            if "body" in s:
                                s["body"] = self._map_subgraph_label_ref(s.get("body"), labels, idmap)
                            if "after" in s:
                                s["after"] = self._map_subgraph_label_ref(s.get("after"), labels, idmap)
            out[new_lid] = body_copy
        return out

    def _include_path_diagnostic(
        self,
        kind: str,
        lineno: int,
        line_node: Dict[str, Any],
        message: str,
        suggested_fix: str,
        source_lines: Sequence[str],
    ) -> Diagnostic:
        span_u, col_u = self._strict_nth_slot_content_char_span(
            line_node, 0, lineno, source_lines
        )
        return Diagnostic(
            lineno=lineno,
            col_offset=col_u,
            kind=kind,
            message=message,
            span=span_u,
            suggested_fix=suggested_fix,
        )

    def _emit_include_diagnostic(
        self,
        *,
        lineno: int,
        line_node: Dict[str, Any],
        message: str,
        suggested_fix: str,
        source_lines: Sequence[str],
        context: Optional[CompilerContext],
    ) -> None:
        """Structured include issue: strict → kind include_failure + legacy error; else include_warning."""
        kind = "include_failure" if self.strict_mode else "include_warning"
        d = self._include_path_diagnostic(
            kind, lineno, line_node, message, suggested_fix, source_lines
        )
        if context is not None:
            context.add(d)
        prefix = f"Line {lineno}: "
        if self.strict_mode:
            self._errors.append(prefix + message)
        else:
            self._warnings.append(prefix + message)

    def _resolved_include_key(self, p: Path) -> str:
        try:
            return str(p.resolve())
        except OSError:
            return str(p)

    def _compile_self_path_key(self, source_path: Optional[str]) -> Optional[str]:
        if not source_path:
            return None
        try:
            return str(Path(source_path).resolve())
        except OSError:
            return None

    @staticmethod
    def _qualify_include_error_label_refs(
        message: str, alias: str, sub_labels: Dict[str, Any]
    ) -> str:
        """Rewrite `Label 'ENTRY'` → `Label 'alias/ENTRY'` in subgraph compile errors (include UX)."""
        if not message or not alias:
            return message
        keys = sorted(
            (str(k) for k in sub_labels.keys() if k is not None and str(k) != "_anon"),
            key=len,
            reverse=True,
        )
        out = str(message)
        for sk in keys:
            out = out.replace(f"Label '{sk}'", f"Label '{alias}/{sk}'")
        return out

    def _process_include_prelude(
        self,
        prelude: List[Tuple[int, Dict[str, Any]]],
        source_lines: List[str],
        context: Optional[CompilerContext],
        parent_source_path: Optional[str],
        include_ancestors: Set[str],
        emit_graph: bool,
    ) -> None:
        """Load and merge subgraphs from leading `include` lines (v1 modules)."""
        self_key = self._compile_self_path_key(parent_source_path)
        ancestor_stack = set(include_ancestors)
        for lineno, line_node in prelude:
            slots = line_node.get("slot_values") or []
            parsed = self._parse_include_directive(list(slots))
            if parsed is None:
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message="invalid `include` directive (expected `include <path> [as <alias>]`)",
                    suggested_fix='Use: include \"modules/common/retry.ainl\" as retry',
                    source_lines=source_lines,
                    context=context,
                )
                continue
            raw_path, alias = parsed
            resolved_path, err_msg = self._resolve_include_path(raw_path, parent_source_path)
            if resolved_path is None or err_msg:
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message=err_msg or "could not resolve include path",
                    suggested_fix="Check the path exists next to the source file or under ./modules/.",
                    source_lines=source_lines,
                    context=context,
                )
                continue
            inc_key = self._resolved_include_key(resolved_path)
            if inc_key in ancestor_stack or (self_key is not None and inc_key == self_key):
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message=f"include cycle detected involving {resolved_path.name!r}",
                    suggested_fix="Remove the circular include chain or merge shared code into one file.",
                    source_lines=source_lines,
                    context=context,
                )
                continue
            try:
                sub_code = resolved_path.read_text(encoding="utf-8")
            except OSError as e:
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message=f"could not read included file: {e}",
                    suggested_fix="Fix file permissions or path.",
                    source_lines=source_lines,
                    context=context,
                )
                continue

            next_ancestors = set(ancestor_stack)
            if self_key:
                next_ancestors.add(self_key)

            # Compile included unit without raising: parent must still run include-contract
            # checks (ENTRY/EXIT_*, no top-level E/S) even when the subgraph has unrelated
            # strict errors, so diagnostics stay actionable.
            sub_compiler = AICodeCompiler(strict_mode=self.strict_mode)
            sub_ir = sub_compiler.compile(
                sub_code,
                emit_graph=emit_graph,
                context=None,
                source_path=str(resolved_path),
                include_ancestors=next_ancestors,
            )

            # --- Phase: include merge (literal hints + lowering) ---
            # - Merge from sub_compiler.labels (pre-IR-export, __literal_fields intact on steps).
            # - Prefix keys to `alias/LABEL` and copy bodies into self.labels.
            # - The parent compiler then runs _steps_to_graph_all() on the combined program.
            # - Do NOT merge from sub_ir["labels"]: that is a deepcopy built for output and has
            #   __literal_fields stripped, so a second lowering would treat J "ok" as a variable.
            sub_labels = sub_compiler.labels or {}
            prefixed = self._prefix_subgraph_labels(sub_labels, alias)
            existing = set(self.labels.keys())
            conflict_keys = sorted(str(k) for k in prefixed if k in existing)

            strict_msgs: List[str] = []
            if self._subgraph_source_has_top_level_e_or_s(sub_code):
                strict_msgs.append(
                    "included subgraph must not declare top-level E or S (endpoint/service) ops"
                )
            strict_msgs.extend(self._subgraph_contract_errors(sub_labels))
            if conflict_keys:
                strict_msgs.append(
                    "included labels conflict with existing labels: "
                    + ", ".join(conflict_keys[:8])
                    + ("..." if len(conflict_keys) > 8 else "")
                )

            compile_errs = [
                self._qualify_include_error_label_refs(str(e), alias, sub_labels)
                for e in (sub_ir.get("errors") or [])
                if e
            ]

            if self.strict_mode and strict_msgs:
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message="; ".join(strict_msgs),
                    suggested_fix="Rename the alias (`as other_name`), remove E/S from the include, "
                    "or fix ENTRY/EXIT_* labels in the included file.",
                    source_lines=source_lines,
                    context=context,
                )
                continue

            if self.strict_mode and compile_errs:
                detail = compile_errs[0]
                if len(compile_errs) > 1:
                    detail = detail + "; " + "; ".join(compile_errs[1:3])
                    if len(compile_errs) > 3:
                        detail += "; ..."
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message=f"included file {resolved_path.name!r} failed strict compilation: {detail}",
                    suggested_fix="Fix diagnostics in the included file or relax strict checks there.",
                    source_lines=source_lines,
                    context=context,
                )
                continue

            if strict_msgs:
                self._emit_include_diagnostic(
                    lineno=lineno,
                    line_node=line_node,
                    message="; ".join(strict_msgs),
                    suggested_fix="Rename the alias (`as other_name`), remove E/S from the include, "
                    "or fix ENTRY/EXIT_* labels in the included file.",
                    source_lines=source_lines,
                    context=context,
                )

            for lk, body in prefixed.items():
                self.labels[str(lk)] = body

    def _diag_label_node_from_message(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        m = self._DIAG_LABEL_NODE_RE.search(message or "")
        if not m:
            return None, None
        return str(m.group(1)), str(m.group(2))

    def _enrich_structured_diagnostics(self, context: CompilerContext) -> None:
        """Attach IR-backed line numbers to structured diagnostics when label+node are known."""
        if not context.diagnostics:
            return
        enriched: List[Diagnostic] = []
        for d in list(context.diagnostics):
            ln = d.lineno
            if d.label_id and d.node_id:
                ir_ln = self._diag_lineno_from_label_node(d.label_id, d.node_id, self.labels)
                if ir_ln is not None:
                    ln = ir_ln
            enriched.append(
                make_diagnostic(
                    lineno=ln,
                    col_offset=d.col_offset,
                    kind=d.kind,
                    message=d.message,
                    span=d.span,
                    label_id=d.label_id,
                    node_id=d.node_id,
                    contract_violation_reason=d.contract_violation_reason,
                    suggested_fix=d.suggested_fix,
                    related_span=d.related_span,
                )
            )
        context.diagnostics.clear()
        context.extend(enriched)

    def _diag_lineno_from_label_node(self, label_id: Optional[str], node_id: Optional[str], labels: Dict[str, Any]) -> Optional[int]:
        if not label_id or not node_id:
            return None
        body = labels.get(str(label_id))
        if not isinstance(body, dict):
            return None
        nodes = body.get("nodes", [])
        if not isinstance(nodes, list):
            return None
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if str(node.get("id", "")) != str(node_id):
                continue
            data = node.get("data", {})
            if isinstance(data, dict):
                lineno = data.get("lineno")
                if isinstance(lineno, int):
                    return lineno
            break
        return None

    def _diag_op_from_message(self, message: str) -> Optional[str]:
        m = self._DIAG_OP_PREFIX_RE.match((message or "").strip())
        if not m:
            return None
        op = m.group(1)
        return MODULE_ALIASES.get(op, op)

    def _diag_lineno_from_op(self, op: Optional[str], cst_lines: Sequence[Dict[str, Any]]) -> Optional[int]:
        if not op:
            return None
        matches: List[int] = []
        for ln in cst_lines:
            if not isinstance(ln, dict):
                continue
            op_value = str(ln.get("op_value", "")).strip()
            if not op_value:
                continue
            canonical = MODULE_ALIASES.get(op_value, op_value)
            if canonical == op:
                lineno = ln.get("lineno")
                if isinstance(lineno, int):
                    matches.append(lineno)
        if len(matches) == 1:
            return matches[0]
        return None

    def _to_structured_diag(
        self, item: Any, severity: str, labels: Dict[str, Any], cst_lines: Sequence[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Convert compiler error/warning items to a structured diagnostic object.
        Keeps backward compatibility by leaving self._errors/self._warnings as strings,
        while exposing structured diagnostics in IR.
        """
        code = "AINL_COMPILE_ERROR" if severity == "error" else "AINL_COMPILE_WARNING"
        out: Dict[str, Any] = {
            "code": code,
            "message": "",
            "severity": severity,
        }

        if isinstance(item, dict):
            # Respect structured fields if callers already provided them.
            out["message"] = str(item.get("message", ""))
            for k in ("code", "label_id", "node_id", "op", "lineno", "span"):
                if k in item:
                    out[k] = item[k]
            if not out["message"]:
                out["message"] = str(item)
        else:
            out["message"] = str(item)

        if "lineno" not in out:
            lineno = self._diag_line_from_message(out["message"])
            if lineno is not None:
                out["lineno"] = lineno

        if "label_id" not in out or "node_id" not in out:
            lid, nid = self._diag_label_node_from_message(out["message"])
            if lid is not None and "label_id" not in out:
                out["label_id"] = lid
            if nid is not None and "node_id" not in out:
                out["node_id"] = nid

        if "lineno" not in out:
            lineno = self._diag_lineno_from_label_node(
                str(out.get("label_id")) if out.get("label_id") is not None else None,
                str(out.get("node_id")) if out.get("node_id") is not None else None,
                labels,
            )
            if lineno is not None:
                out["lineno"] = lineno

        if "op" not in out:
            op = self._diag_op_from_message(out["message"])
            if op:
                out["op"] = op

        if "lineno" not in out:
            lineno = self._diag_lineno_from_op(
                str(out.get("op")) if out.get("op") is not None else None,
                cst_lines,
            )
            if lineno is not None:
                out["lineno"] = lineno

        if "span" not in out and isinstance(out.get("lineno"), int):
            ln = int(out["lineno"])
            out["span"] = {"line": ln, "col_start": 0, "col_end": 0}

        return out

    def _build_structured_diagnostics(
        self, labels: Dict[str, Any], cst_lines: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for err in list(self._errors):
            out.append(self._to_structured_diag(err, "error", labels, cst_lines))
        for warn in list(self._warnings):
            out.append(self._to_structured_diag(warn, "warning", labels, cst_lines))
        return out

    def _line_content_span(self, line_node: Dict[str, Any]) -> Optional[Dict[str, int]]:
        tokens = [
            t
            for t in (line_node.get("tokens") or [])
            if isinstance(t, dict) and t.get("kind") in ("bare", "string")
        ]
        if not tokens:
            return None
        first = tokens[0].get("span") or {}
        last = tokens[-1].get("span") or {}
        line = line_node.get("lineno")
        if not isinstance(line, int):
            return None
        start = int(first.get("col_start", 0) or 0)
        end = int(last.get("col_end", start) or start)
        return {"line": line, "col_start": start, "col_end": end}

    def _append_canonical_warning(
        self,
        message: str,
        *,
        code: str,
        line_node: Dict[str, Any],
        op: Optional[str] = None,
    ) -> None:
        item: Dict[str, Any] = {
            "code": code,
            "message": message,
            "lineno": line_node.get("lineno"),
            "op": op or line_node.get("op_canonical") or line_node.get("op_value"),
        }
        span = self._line_content_span(line_node)
        if span is not None:
            item["span"] = span
        self._warnings.append(item)

    def _append_canonical_lint_warnings(self, cst_lines: Sequence[Dict[str, Any]]) -> None:
        compatible_ops = {
            "Filt",
            "Sort",
            "X",
            "Loop",
            "While",
            "CacheGet",
            "CacheSet",
            "QueuePut",
            "Tx",
            "Enf",
        }
        seen: Set[Tuple[str, int, str]] = set()

        def warn(message: str, *, code: str, line_node: Dict[str, Any], op: Optional[str] = None) -> None:
            lineno = int(line_node.get("lineno", 0) or 0)
            key = (code, lineno, message)
            if key in seen:
                return
            seen.add(key)
            self._append_canonical_warning(message, code=code, line_node=line_node, op=op)

        for line_node in cst_lines:
            op = str(line_node.get("op_canonical") or line_node.get("op_value") or "").strip()
            slots = list(line_node.get("slot_values") or [])
            if not op and not slots:
                continue

            if op.startswith("L") and op.endswith(":") and slots:
                warn(
                    "Canonical lint: inline executable content after a label declaration is compatibility syntax; "
                    "prefer a label-only line followed by indented step lines.",
                    code="AINL_CANONICAL_INLINE_LABEL",
                    line_node=line_node,
                    op="L:",
                )

            if op == "R" and slots:
                adapter = str(slots[0]).strip()
                if adapter and "." not in adapter:
                    warn(
                        "Canonical lint: split-token request form is compatibility syntax; prefer "
                        "`R adapter.VERB target [args...] ->out`.",
                        code="AINL_CANONICAL_R_SPLIT_FORM",
                        line_node=line_node,
                    )
                elif "." in adapter:
                    _, verb = adapter.split(".", 1)
                    if verb and verb != verb.upper():
                        warn(
                            "Canonical lint: prefer uppercase dotted adapter verbs in canonical examples "
                            "(for example `core.ADD`, `http.GET`).",
                            code="AINL_CANONICAL_LOWERCASE_VERB",
                            line_node=line_node,
                        )

            if op == "Call":
                has_out = any(isinstance(slot, str) and slot.startswith("->") for slot in slots[1:])
                if not has_out:
                    warn(
                        "Canonical lint: prefer explicit `Call Lx ->out` binding over compatibility fallback behavior.",
                        code="AINL_CANONICAL_CALL_EXPLICIT_OUT",
                        line_node=line_node,
                    )

            if op in compatible_ops:
                warn(
                    f"Canonical lint: `{op}` is currently accepted as a compatibility surface, not the recommended canonical core.",
                    code="AINL_CANONICAL_COMPAT_OP",
                    line_node=line_node,
                )

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
        String decoding treats \\", \\\\, \\n, \\t, \\r as escape sequences.
        Raises ValueError with line+column for unterminated strings.
        """
        _ESC_MAP = {'"': '"', '\\': '\\', 'n': '\n', 't': '\t', 'r': '\r'}
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
                if ch == "\\" and i + 1 < n and line[i + 1] in _ESC_MAP:
                    esc = True
                    i += 1
                    continue
                if ch == '"':
                    i += 1
                    raw = line[col_start:i]
                    value_parts: List[str] = []
                    j = col_start + 1
                    while j < i - 1:
                        if line[j] == "\\" and j + 1 < i - 1 and line[j + 1] in _ESC_MAP:
                            value_parts.append(_ESC_MAP[line[j + 1]])
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
        slot_kinds = [t["kind"] for t in content[1:]] if len(content) > 1 else []
        token_ser = [{"kind": t["kind"], "raw": t["raw"], "value": t["value"], "span": t["span"]} for t in tokens]
        line_no = lineno if lineno is not None else (tokens[0]["span"]["line"] if tokens else 1)
        return {
            "lineno": line_no,
            "original_line": raw_line,
            "op_value": op_value,
            "op_canonical": "",
            "slot_values": slot_values,
            "slot_kinds": slot_kinds,
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
    STEP_OPS = frozenset(
        {
            "R",
            "J",
            "If",
            "Err",
            "Retry",
            "Call",
            "Set",
            "Filt",
            "Sort",
            "X",
            "Loop",
            "While",
            "CacheGet",
            "CacheSet",
            "QueuePut",
            "Tx",
            "Enf",
        }
    )

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

    def _normalize_if_target(self, tok: Optional[str], allow_fallback: bool = False) -> Optional[str]:
        """Normalize If branch target tokens to a canonical label id string."""
        if tok is None:
            return None
        lid = self._parse_arrow_lbl(tok)
        if lid is not None:
            return lid
        if not allow_fallback:
            return None
        s = str(tok)
        if s.startswith("->"):
            s = s[2:]
        if s.startswith("L"):
            s = s[1:]
        if ":" in s:
            s = s.split(":")[-1]
        return s or None

    @staticmethod
    def _parse_at_node_id(tok: str) -> Optional[str]:
        """Parse @n<num> or n<num> to canonical node id (e.g. n3); else None. For Err/Retry target."""
        if not tok or not isinstance(tok, str):
            return None
        s = tok.strip()
        if s.startswith("@"):
            s = s[1:]
        if not s.startswith("n"):
            return None
        rest = s[1:]
        if not rest.isdigit():
            return None
        return "n" + str(int(rest))

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

    def _analyze_step_rw(self, s: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Best-effort static analysis of frame reads/writes for a legacy step."""
        op = s.get("op")
        reads: List[str] = []
        writes: List[str] = []
        literal_fields = s.get("__literal_fields") or {}

        def _is_runtime_literal(tok: Any) -> bool:
            if tok is None:
                return True
            if isinstance(tok, (int, float, bool)):
                return True
            if not isinstance(tok, str):
                return False
            t = tok.strip()
            if t in ("", "true", "false", "null"):
                return True
            if t.startswith("$"):
                return False
            if t.isdigit() or (t.startswith("-") and t[1:].isdigit()):
                return True
            s2 = t[1:] if t.startswith("-") else t
            if "." in s2 and s2.replace(".", "", 1).isdigit():
                return True
            if any(ch in s2 for ch in ("e", "E")):
                try:
                    float(t)
                    return True
                except Exception:
                    pass
            return False

        def _add_read_if_var(tok: Any, field_name: Optional[str] = None) -> None:
            if tok is None:
                return
            if field_name and bool(literal_fields.get(field_name)):
                return
            if isinstance(tok, str) and tok.startswith("$"):
                reads.append(tok[1:])
                return
            if _is_runtime_literal(tok):
                return
            reads.append(str(tok))

        if op == "R":
            out_var = s.get("out", "res")
            if out_var:
                writes.append(str(out_var))
        elif op == "J":
            var = s.get("var", "data")
            if var:
                _add_read_if_var(var, "var")
        elif op == "Set":
            ref = s.get("ref")
            name = s.get("name")
            _add_read_if_var(ref, "ref")
            if name:
                writes.append(str(name))
        elif op == "Filt":
            ref = s.get("ref")
            name = s.get("name")
            _add_read_if_var(ref, "ref")
            _add_read_if_var(s.get("value"), "value")
            if name:
                writes.append(str(name))
        elif op == "Sort":
            ref = s.get("ref")
            name = s.get("name")
            _add_read_if_var(ref, "ref")
            if name:
                writes.append(str(name))
        elif op == "Call":
            out_var = s.get("out") or "_call_result"
            if out_var:
                writes.append(str(out_var))
        elif op == "If":
            cond = s.get("cond", "")
            if isinstance(cond, str) and cond:
                base = cond
                if base.endswith("?"):
                    base = base[:-1]
                if "=" in base:
                    base = base.split("=", 1)[0]
                if base:
                    reads.append(base.strip())
        elif op == "CacheGet":
            key = s.get("key")
            fallback = s.get("fallback")
            out_var = s.get("out", "data")
            _add_read_if_var(key, "key")
            _add_read_if_var(fallback, "fallback")
            if out_var:
                writes.append(str(out_var))
        elif op == "CacheSet":
            key = s.get("key")
            value = s.get("value")
            _add_read_if_var(key, "key")
            _add_read_if_var(value, "value")
        elif op == "QueuePut":
            value = s.get("value")
            out_var = s.get("out")
            _add_read_if_var(value, "value")
            if out_var:
                writes.append(str(out_var))
        elif op == "Tx":
            action = (s.get("action") or "begin").lower()
            if action == "begin":
                writes.append("_txid")
        elif op == "Enf":
            # Policy enforcement typically inspects auth/role context.
            reads.extend(["_auth_present", "_role"])

        # De-duplicate while preserving order
        seen_r: set = set()
        seen_w: set = set()
        r_out: List[str] = []
        w_out: List[str] = []
        for v in reads:
            if v not in seen_r:
                seen_r.add(v)
                r_out.append(v)
        for v in writes:
            if v not in seen_w:
                seen_w.add(v)
                w_out.append(v)
        return r_out, w_out

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
            effect = "io" if op in ("R", "Call", "CacheSet", "QueuePut", "Tx") else ("meta" if op in ("Err", "Retry") else "pure")
            reads, writes = self._analyze_step_rw(s)
            node = {
                "id": nid,
                "op": op,
                "effect": effect,
                "reads": reads,
                "writes": writes,
                "lineno": s.get("lineno"),
                "data": s,
            }
            nodes.append(node)
            if op == "If":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
                then_id = self._norm_lid(s.get("then"))
                else_id = self._norm_lid(s.get("else"))
                if then_id:
                    edges.append({"from": nid, "to": then_id, "port": "then", "to_kind": "label"})
                if else_id:
                    edges.append({"from": nid, "to": else_id, "port": "else", "to_kind": "label"})
                last_nid = None
            elif op == "Loop":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
                body_id = self._norm_lid(s.get("body"))
                after_id = self._norm_lid(s.get("after"))
                if body_id:
                    edges.append({"from": nid, "to": body_id, "port": "body", "to_kind": "label"})
                if after_id:
                    edges.append({"from": nid, "to": after_id, "port": "after", "to_kind": "label"})
                last_nid = None
            elif op == "While":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
                body_id = self._norm_lid(s.get("body"))
                after_id = self._norm_lid(s.get("after"))
                if body_id:
                    edges.append({"from": nid, "to": body_id, "port": "body", "to_kind": "label"})
                if after_id:
                    edges.append({"from": nid, "to": after_id, "port": "after", "to_kind": "label"})
                last_nid = None
            elif op == "Err":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
                node_ids_so_far = {n["id"] for n in nodes[:-1]}
                source_for_err = s.get("at_node_id")
                if source_for_err:
                    norm = self._parse_at_node_id(source_for_err) or source_for_err
                    if norm not in node_ids_so_far:
                        self._errors.append(
                            f"Label {lid!r}: Err at_node_id={source_for_err!r} must reference a prior node in this label (available: {sorted(node_ids_so_far)!r})"
                        )
                        source_for_err = last_nid
                    else:
                        source_for_err = norm
                else:
                    source_for_err = last_nid
                if source_for_err:
                    edges.append({"from": source_for_err, "to": nid, "port": "err", "to_kind": "node"})
                handler = self._norm_lid(s.get("handler"))
                if handler:
                    edges.append({"from": nid, "to": handler, "to_kind": "label", "port": "handler"})
                # Err is metadata. Keep linear flow connected to subsequent steps.
                last_nid = nid
            elif op == "Retry":
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
                node_ids_so_far = {n["id"] for n in nodes[:-1]}
                source_for_retry = s.get("at_node_id")
                if source_for_retry:
                    norm = self._parse_at_node_id(source_for_retry) or source_for_retry
                    if norm not in node_ids_so_far:
                        self._errors.append(
                            f"Label {lid!r}: Retry at_node_id={source_for_retry!r} must reference a prior node in this label (available: {sorted(node_ids_so_far)!r})"
                        )
                        source_for_retry = last_nid
                    else:
                        source_for_retry = norm
                else:
                    source_for_retry = last_nid
                if source_for_retry:
                    edges.append({"from": source_for_retry, "to": nid, "port": "retry", "to_kind": "node"})
                last_nid = nid
            else:
                if last_nid:
                    edges.append({"from": last_nid, "to": nid, "to_kind": "node", "port": "next"})
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

    def _validate_graphs(self) -> None:
        """Strict-mode graph validation: canonical node ids, entry/exits, and reachability.

        These checks assume graphs were produced by _steps_to_graph_all() and are intended
        to enforce the spec's canonical graph invariants in strict mode (§3.5).
        """
        endpoint_entry_defs: Dict[str, Set[str]] = {}
        core0 = self.services.get("core") or {}
        for _path, _method, ep in _iter_eps(core0.get("eps") or {}):
            nl = self._norm_lid(ep.get("label_id", ""))
            if nl and ep.get("return_var"):
                endpoint_entry_defs.setdefault(nl, set()).add(ep["return_var"])
        entry_var_map = propagate_inter_label_entry_defs(
            self.labels,
            norm_lid=self._norm_lid,
            endpoint_entry_defs=endpoint_entry_defs or None,
        )
        for lid, body in self.labels.items():
            nodes: List[Dict[str, Any]] = body.get("nodes") or []
            edges: List[Dict[str, Any]] = body.get("edges") or []
            if not nodes:
                # Allow empty graphs; step/endpoint validations handle semantic issues.
                continue

            node_ids = [n.get("id") for n in nodes]
            node_id_set = set(node_ids)

            # Basic node field invariants: effect/reads/writes shape.
            for n in nodes:
                effect = n.get("effect")
                if effect not in ("io", "pure", "meta"):
                    self._errors.append(
                        f"Label {lid!r}: node {n.get('id')!r} has invalid effect {effect!r} (must be 'io', 'pure', or 'meta')"
                    )
                reads = n.get("reads")
                writes = n.get("writes")
                if not isinstance(reads, list) or not isinstance(writes, list):
                    self._errors.append(
                        f"Label {lid!r}: node {n.get('id')!r} must have list reads/writes fields"
                    )
                # Strict: R nodes must use a known adapter.verb (adapter contract).
                if self.strict_mode and n.get("op") == "R":
                    data = n.get("data") or {}
                    key = strict_adapter_key_for_step(data)
                    if key and not strict_adapter_is_allowed(key):
                        self._errors.append(
                            f"Label {lid!r}: node {n.get('id')!r} uses unknown adapter.verb {key!r} (strict adapter contract)"
                        )

            # Canonical ids must be n1..nK with no gaps or duplicates.
            if any(not isinstance(nid, str) or not nid.startswith("n") for nid in node_ids):
                self._errors.append(f"Label {lid!r}: graph nodes must use canonical ids n1..nK")
            else:
                expected_ids = {f"n{i}" for i in range(1, len(node_ids) + 1)}
                if node_id_set != expected_ids:
                    self._errors.append(
                        f"Label {lid!r}: graph node ids must be contiguous n1..n{len(node_ids)}, "
                        f"got {sorted(node_id_set)!r}"
                    )

            # Entry must exist and point at a known node when graph is non-empty.
            entry = body.get("entry")
            if entry is None:
                self._errors.append(f"Label {lid!r}: non-empty graph must have an entry node")
            elif entry not in node_id_set:
                self._errors.append(
                    f"Label {lid!r}: entry {entry!r} not found in graph node ids {sorted(node_id_set)!r}"
                )

            # Exits must align with J nodes (one exit per J, matching var).
            exits = body.get("exits") or []
            j_nodes = [n for n in nodes if n.get("op") == "J"]
            id_to_jvar = {
                n["id"]: (n.get("data") or {}).get("var", "data")
                for n in j_nodes
                if isinstance(n.get("id"), str)
            }

            for ex in exits:
                nid = ex.get("node")
                var = ex.get("var")
                if nid not in id_to_jvar:
                    self._errors.append(
                        f"Label {lid!r}: exit references non-J node {nid!r} (exits must point at J nodes)"
                    )
                    continue
                j_var = id_to_jvar[nid]
                if var is not None and var != j_var:
                    self._errors.append(
                        f"Label {lid!r}: exit var {var!r} for node {nid!r} does not match J var {j_var!r}"
                    )

            for nid, j_var in id_to_jvar.items():
                if not any(ex.get("node") == nid for ex in exits):
                    self._errors.append(
                        f"Label {lid!r}: J node {nid!r} (var={j_var!r}) missing from exits list"
                    )

            # Node-to-node edges must reference valid ids; also build adjacency for reachability.
            # Enforce port present and valid for source op.
            node_by_id = {n.get("id"): n for n in nodes if n.get("id")}
            for e in edges:
                port = e.get("port")
                if port is None or port == "":
                    self._errors.append(
                        f"Label {lid!r}: edge from={e.get('from')!r} to={e.get('to')!r} missing port"
                    )
                else:
                    from_node = node_by_id.get(e.get("from"))
                    allowed = GRAPH_VALID_PORTS.get(from_node.get("op") if from_node else None, DEFAULT_PORTS)
                    if port not in allowed:
                        op_name = from_node.get("op") if from_node else "?"
                        self._errors.append(
                            f"Label {lid!r}: edge from={e.get('from')!r} port={port!r} invalid for op "
                            f"{op_name!r} (allowed: {sorted(allowed)!r})"
                        )

            adj: Dict[str, set] = {nid: set() for nid in node_id_set}
            for e in edges:
                if e.get("to_kind") != "node":
                    continue
                src = e.get("from")
                dst = e.get("to")
                if src not in node_id_set or dst not in node_id_set:
                    self._errors.append(
                        f"Label {lid!r}: edge with invalid node reference from={src!r} to={dst!r}"
                    )
                    continue
                adj.setdefault(src, set()).add(dst)

            # Reachability: every node in a non-empty graph should be reachable from entry.
            if isinstance(entry, str) and entry in node_id_set:
                reachable: set = set()
                stack: List[str] = [entry]
                while stack:
                    cur = stack.pop()
                    if cur in reachable:
                        continue
                    reachable.add(cur)
                    for nxt in adj.get(cur, ()):
                        if nxt not in reachable:
                            stack.append(nxt)
                for nid in sorted(node_id_set):
                    if nid not in reachable:
                        self._errors.append(
                            f"Label {lid!r}: graph node {nid!r} is unreachable from entry {entry!r}"
                        )

            # Optional strict: defined-before-use along success paths (intra- + inter-label).
            if isinstance(entry, str) and entry in node_id_set:
                merged_entry = set(entry_var_map.get(str(lid), set()))
                violations = dataflow_defined_before_use(
                    nodes, edges, entry, merged_entry if merged_entry else None
                )
                for nid, var in violations:
                    msg = (
                        f"Label {lid!r}: node {nid!r} reads {var!r} which may be undefined on this path"
                        f" (if this is a string literal in strict mode, quote it explicitly)"
                    )
                    # Include-aware hint: merged subgraph labels use `alias/NAME` keys.
                    if "/" in str(lid):
                        inc_alias = str(lid).split("/", 1)[0]
                        msg += (
                            f" (Label `{lid}` looks like an included subgraph merged as `{inc_alias}`; "
                            f"check jumps and variables in that module, or quote string literals.)"
                        )
                    self._errors.append(msg)

            # Call / control-flow effect inclusion: callee label effects must be subset of caller.
            # Loop/While jump to body/after labels; those callees' effects are not in the caller's
            # local effect_summary, so expand the allowed set with all label targets from the same
            # Loop/While/Call node (and Call remains a single target).
            if self.strict_mode:
                caller_effects = set((body.get("effect_summary") or {}).get("effects") or [])
                for e in edges:
                    if e.get("to_kind") != "label":
                        continue
                    callee_lid = self._norm_lid(e.get("to", ""))
                    if not callee_lid or callee_lid not in self.labels:
                        continue
                    callee_body = self.labels.get(callee_lid) or {}
                    callee_effects = set((callee_body.get("effect_summary") or {}).get("effects") or [])
                    eff_caller = set(caller_effects)
                    from_node = node_by_id.get(e.get("from"))
                    from_op = (from_node or {}).get("op")
                    from_id = from_node.get("id") if from_node else None
                    if from_op in ("Loop", "While", "If") and from_id:
                        for e2 in edges:
                            if e2.get("from") != from_id or e2.get("to_kind") != "label":
                                continue
                            tl = self._norm_lid(e2.get("to", ""))
                            if not tl or tl not in self.labels:
                                continue
                            tl_body = self.labels.get(tl) or {}
                            eff_caller |= set((tl_body.get("effect_summary") or {}).get("effects") or [])
                    if callee_effects and not (callee_effects <= eff_caller):
                        extra = callee_effects - eff_caller
                        self._errors.append(
                            f"Label {lid!r}: Call to label {callee_lid!r} has effects {sorted(extra)!r} not allowed in caller"
                        )

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

    def _has_nonempty_rag(self) -> bool:
        rag = self.rag or {}
        if not isinstance(rag, dict):
            return False
        return any(bool(v) for v in rag.values())

    def _iter_all_steps(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for _lid, body in (self.labels or {}).items():
            legacy = (body or {}).get("legacy") or {}
            for step in (legacy.get("steps") or []):
                if isinstance(step, dict):
                    out.append(step)
        return out

    def _compute_emit_capabilities(self) -> Dict[str, bool]:
        services = self.services or {}
        core = services.get("core") or {}
        core_mode = (core or {}).get("mode")
        core_eps = bool((core or {}).get("eps"))
        fe = services.get("fe") or {}
        has_fe_surface = bool(fe) and any(
            bool(fe.get(k))
            for k in ("ui", "routes", "layouts", "forms", "tables", "events", "components", "bindings")
        )
        has_types = bool(self.types)
        has_cron = bool(self.crons) or core_mode == "cron"
        has_scraper = bool(((services.get("scrape") or {}).get("defs") or {}))
        steps = self._iter_all_steps()
        has_mt5_step = any(str((s.get("adapter") or "")).lower().startswith("mt5.") for s in steps)
        has_mt5_service = "mt5" in services
        has_mt5 = has_mt5_service or has_mt5_step
        rag_active = self._has_nonempty_rag()
        has_user_labels = any(lid != "_anon" for lid in (self.labels or {}).keys())
        # Backend need is explicit from endpoint/core-web/rag, plus plain label programs
        # that are not clearly specialized as scraper/mt5/cron-only workflows.
        needs_python_api = bool(
            core_eps
            or core_mode == "web"
            or rag_active
            or (has_user_labels and not (has_scraper or has_mt5 or has_cron))
        )
        hybrid = services.get("hybrid") or {}
        hy_emit = hybrid.get("emit") if isinstance(hybrid.get("emit"), list) else []
        needs_langgraph = "langgraph" in hy_emit
        needs_temporal = "temporal" in hy_emit
        return {
            "needs_react_ts": has_fe_surface,
            "needs_python_api": needs_python_api,
            "needs_prisma": has_types,
            "needs_mt5": has_mt5,
            "needs_scraper": has_scraper,
            "needs_cron": has_cron,
            "needs_langgraph": needs_langgraph,
            "needs_temporal": needs_temporal,
        }

    def _compute_required_emit_targets(self, emit_capabilities: Dict[str, bool]) -> Dict[str, List[str]]:
        minimal_emit = [t for t in FULL_EMIT_TARGET_ORDER if emit_capabilities.get(f"needs_{t}", False)]
        return {
            "full_multitarget": list(FULL_EMIT_TARGET_ORDER),
            "minimal_emit": minimal_emit or ["python_api"],
        }

    def compile(
        self,
        code: str,
        emit_graph: bool = True,
        *,
        context: Optional[CompilerContext] = None,
        source_path: Optional[str] = None,
        include_ancestors: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        source_text = code
        lines = code.split("\n")
        source_lines = list(lines)
        if context is not None:
            context.reset_for_compile(source_text, source_path=source_path)
        path_for_includes = context.source_path if context is not None else source_path
        prelude_includes, prelude_linenos = self._scan_include_prelude(lines)
        cst_lines: List[Dict[str, Any]] = []
        parsed_ops = 0
        # Reset compiler state for deterministic multi-compile usage (eval/benchmark loops).
        self.services = {}
        self.labels = {}
        self._label_decl_lines = {}
        self.types = {}
        self.crons = []
        self.current_ui = None
        self.current_label = None
        self.config = {"env": [], "secrets": []}
        self.observability = {"metrics": [], "trace": False}
        self.deploy = {"strategy": "rolling", "env_target": "", "flags": []}
        self.limits = {"per_path": {}, "per_tenant": 0}
        self.roles = []
        self.allow = []
        self.audit = {}
        self.admin = {}
        self.desc = {"endpoints": {}, "types": {}}
        self.runbooks = {}
        self.ver = None
        self.compat = None
        self.tests = []
        self.api_opts = {"style": "rest", "version_prefix": "", "deprecate": [], "sla": {}}
        self._current_test = None
        self.rag = {
            "sources": {},
            "chunking": {},
            "embeddings": {},
            "stores": {},
            "indexes": {},
            "retrievers": {},
            "augment": {},
            "generate": {},
            "pipelines": {},
        }
        self.capabilities = {"auth": {}, "policy": {}, "cache": {}, "queue": {}, "txn": {}}
        self._errors = []
        self._warnings = []
        self.meta = []
        self._process_include_prelude(
            prelude_includes,
            source_lines,
            context,
            path_for_includes,
            set(include_ancestors or ()),
            emit_graph,
        )
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
            slot_kinds = line_node.get("slot_kinds", [])
            if lineno in prelude_linenos:
                op0 = MODULE_ALIASES.get(op_value, op_value)
                line_node["op_canonical"] = op0
                continue
            if not op_value and not slots:
                continue
            parsed_ops += 1
            op = MODULE_ALIASES.get(op_value, op_value)
            line_node["op_canonical"] = op
            mod, mop = None, None
            if "." in op:
                mod, mop = op.split(".", 1)
                if self.strict_mode and mod not in KNOWN_MODULES:
                    # Phase 2: structured diagnostic + legacy string
                    msg = f"Line {lineno}: unknown module {mod!r} in {op!r}"
                    span_u, col_u = self._strict_op_token_char_span(line_node, lineno, source_lines)
                    if context is not None:
                        # Phase 2: native structured diagnostic + legacy string (unknown module).
                        context.diagnostics.append(
                            Diagnostic(
                                lineno=lineno,
                                col_offset=col_u,
                                kind="strict_validation_failure",
                                message=msg,
                                span=span_u,
                                label_id=None,
                                node_id=None,
                                contract_violation_reason=(
                                    f"Unknown module prefix {mod!r} (allowed: {sorted(KNOWN_MODULES)!r})."
                                ),
                                suggested_fix=(
                                    f"Use one of the supported module prefixes: "
                                    f"{', '.join(sorted(KNOWN_MODULES))}."
                                ),
                                related_span=None,
                            )
                        )
                    self._errors.append(f"Line {lineno}: unknown module {mod!r} in {op!r}")
            spec = self._op_spec(op)
            min_slots = int(spec.get("min_slots", 0))
            if min_slots and len(slots) < min_slots:
                self.meta.append(self._meta_record(lineno, line_node, reason="arity"))
                if self.strict_mode:
                    # Phase 2: structured diagnostic + legacy string
                    msg = f"Line {lineno}: op {op!r} requires at least {min_slots} slots, got {len(slots)}"
                    span_a, col_a = self._strict_op_token_char_span(line_node, lineno, source_lines)
                    if context is not None:
                        # Phase 2: native structured diagnostic + legacy string (arity / min_slots).
                        need = min_slots - len(slots)
                        context.diagnostics.append(
                            Diagnostic(
                                lineno=lineno,
                                col_offset=col_a,
                                kind="strict_validation_failure",
                                message=msg,
                                span=span_a,
                                label_id=None,
                                node_id=None,
                                contract_violation_reason=(
                                    f"Operation '{op}' requires at least {min_slots} argument slot(s), "
                                    f"but only {len(slots)} provided."
                                ),
                                suggested_fix=(
                                    f"Add {need} more slot(s) after '{op}' to satisfy the contract "
                                    f"(e.g. {op} {' '.join(['arg'] * min_slots)})."
                                ),
                                related_span=None,
                            )
                        )
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
                # Deployment hint: opt hybrid benchmark/planner targets into minimal_emit (see _compute_emit_capabilities).
                # Usage: S hybrid langgraph | temporal | langgraph temporal (order-free, de-duped).
                if len(slots) >= 2 and slots[0] == "hybrid":
                    hy = self.services.setdefault("hybrid", {"emit": []})
                    if not isinstance(hy.get("emit"), list):
                        hy["emit"] = []
                    seen = set(hy["emit"])
                    for tok in slots[1:]:
                        if tok in ("langgraph", "temporal"):
                            if tok not in seen:
                                hy["emit"].append(tok)
                                seen.add(tok)
                        elif getattr(self, "strict_mode", False):
                            self._errors.append(
                                f"Line {lineno}: S hybrid unknown target {tok!r}; allowed: langgraph, temporal"
                            )
                    continue
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
                if self.strict_mode:
                    # Phase 2: structured diagnostic + new strict-only legacy error for duplicates.
                    # Human approved: reject second Lxx: in strict (non-strict still merges bodies);
                    # track first decl lineno in _label_decl_lines; keep populating self.labels for IR.
                    if label in self._label_decl_lines:
                        first_lineno = self._label_decl_lines[label]
                        msg = (
                            f"Line {lineno}: duplicate label declaration L{label}: "
                            f"(previously declared on line {first_lineno})"
                        )
                        span_d, col_d = self._strict_op_token_char_span(line_node, lineno, source_lines)
                        related = self._strict_label_decl_line_char_span(label, cst_lines, source_lines)
                        next_free = self._strict_next_free_numeric_label_id()
                        if context is not None:
                            # Phase 2: native structured diagnostic + legacy string (duplicate label).
                            context.diagnostics.append(
                                Diagnostic(
                                    lineno=lineno,
                                    col_offset=col_d,
                                    kind="duplicate_label",
                                    message=msg,
                                    span=span_d,
                                    label_id=label,
                                    node_id=None,
                                    contract_violation_reason=(
                                        f"Label {label!r} was already declared; strict mode rejects "
                                        f"ambiguous duplicate declarations."
                                    ),
                                    suggested_fix=(
                                        f"Rename this block to L{next_free}: or merge steps into the existing "
                                        f"L{label}: (declared on line {first_lineno})."
                                    ),
                                    related_span=related,
                                )
                            )
                        self._errors.append(msg)
                    else:
                        self._label_decl_lines[label] = lineno
                self.current_label = label
                self._ensure_label(label)
                self.labels[label]["slots"] = slots
                leg = self.labels[label]["legacy"]
                # Parse inline steps: R ... J var | If | Set | Filt | Sort | Err | Retry | Call | capability steps
                i = 0
                step_ops = (
                    "R",
                    "J",
                    "If",
                    "Set",
                    "Filt",
                    "Sort",
                    "X",
                    "Loop",
                    "While",
                    "Err",
                    "Retry",
                    "Call",
                    "CacheGet",
                    "CacheSet",
                    "QueuePut",
                    "Tx",
                    "Enf",
                )
                while i < len(slots):
                    if slots[i] == "R":
                        r_slots = []
                        i += 1
                        while i < len(slots) and slots[i] not in step_ops:
                            r_slots.append(slots[i])
                            i += 1
                        parsed = self._parse_req_slots(r_slots)
                        leg["steps"].append({"op": "R", "lineno": lineno, **(parsed or {"raw": r_slots})})
                    elif slots[i] == "J":
                        var = slots[i + 1] if i + 1 < len(slots) else "data"
                        leg["steps"].append({"op": "J", "lineno": lineno, "var": var})
                        i += 2
                    elif slots[i] == "If" and i + 2 < len(slots):
                        cond = slots[i + 1]
                        # Mirror standalone If parsing (single-pass op == "If") so inline and
                        # multiline programs get identical IR (e.g. If c L2 3 → else branch "3").
                        then_l = self._normalize_if_target(slots[i + 2], allow_fallback=True)
                        else_l = (
                            self._normalize_if_target(slots[i + 3], allow_fallback=True)
                            if len(slots) > i + 3
                            else None
                        )
                        if self.strict_mode and then_l is None:
                            self._errors.append(f"Line {lineno}: If then target must be ->L<n> or L<n>, got {slots[i + 2]!r}")
                        leg["steps"].append({"op": "If", "lineno": lineno, "cond": cond, "then": then_l, "else": else_l})
                        i += 4 if len(slots) > i + 3 else 3
                    elif slots[i] == "Set" and i + 3 <= len(slots):
                        step = {"op": "Set", "lineno": lineno, "name": slots[i + 1], "ref": slots[i + 2]}
                        if i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string":
                            step["__literal_fields"] = {"ref": True}
                        leg["steps"].append(step)
                        i += 3
                    elif slots[i] in ("Filt", "Filter") and i + 6 <= len(slots):
                        step = {"op": "Filt", "lineno": lineno, "name": slots[i + 1], "ref": slots[i + 2], "field": slots[i + 3], "cmp": slots[i + 4], "value": slots[i + 5]}
                        lit_fields = {}
                        if i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string":
                            lit_fields["ref"] = True
                        if i + 5 < len(slot_kinds) and slot_kinds[i + 5] == "string":
                            lit_fields["value"] = True
                        if lit_fields:
                            step["__literal_fields"] = lit_fields
                        leg["steps"].append(step)
                        i += 6
                    elif slots[i] == "Sort" and i + 4 <= len(slots):
                        # Sort name ref field [asc|desc]: need 4 tokens min, optional 5th for order (fix #4).
                        order = slots[i + 4] if (i + 4 < len(slots) and slots[i + 4] in ("asc", "desc")) else "asc"
                        step = {"op": "Sort", "lineno": lineno, "name": slots[i + 1], "ref": slots[i + 2], "field": slots[i + 3], "order": order}
                        if i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string":
                            step["__literal_fields"] = {"ref": True}
                        leg["steps"].append(step)
                        i += 5 if (i + 4 < len(slots) and slots[i + 4] in ("asc", "desc")) else 4
                    elif slots[i] == "Err" and i + 1 < len(slots):
                        at_node = self._parse_at_node_id(slots[i + 1])
                        if at_node is not None:
                            if i + 2 >= len(slots):
                                if self.strict_mode:
                                    self._errors.append(f"Line {lineno}: Err @node_id requires handler (e.g. ->L9)")
                                i += 2
                            else:
                                h_id = self._parse_arrow_lbl(slots[i + 2])
                                step = {"op": "Err", "lineno": lineno, "handler": h_id or slots[i + 2].lstrip("L").split(":")[-1], "at_node_id": at_node}
                                leg["steps"].append(step)
                                i += 3
                        else:
                            h_id = self._parse_arrow_lbl(slots[i + 1])
                            leg["steps"].append({"op": "Err", "lineno": lineno, "handler": h_id or slots[i + 1].lstrip("L").split(":")[-1]})
                            i += 2
                    elif slots[i] == "Retry":
                        at_node = self._parse_at_node_id(slots[i + 1]) if i + 1 < len(slots) else None
                        if at_node is not None:
                            count = slots[i + 2] if i + 2 < len(slots) else "3"
                            backoff = slots[i + 3] if i + 3 < len(slots) else "0"
                            strategy = slots[i + 4] if i + 4 < len(slots) and slots[i + 4] in ("fixed", "exponential") else None
                            step_d: Dict[str, Any] = {"op": "Retry", "lineno": lineno, "count": count, "backoff_ms": backoff, "at_node_id": at_node}
                            if strategy:
                                step_d["backoff_strategy"] = strategy
                            leg["steps"].append(step_d)
                            consumed = 2 + (1 if i + 2 < len(slots) else 0) + (1 if i + 3 < len(slots) else 0) + (1 if strategy else 0)
                            i += consumed
                        else:
                            count = slots[i + 1] if i + 1 < len(slots) else "3"
                            backoff = slots[i + 2] if i + 2 < len(slots) else "0"
                            strategy = slots[i + 3] if i + 3 < len(slots) and slots[i + 3] in ("fixed", "exponential") else None
                            step_d = {"op": "Retry", "lineno": lineno, "count": count, "backoff_ms": backoff}
                            if strategy:
                                step_d["backoff_strategy"] = strategy
                            leg["steps"].append(step_d)
                            consumed = 1 + (1 if i + 1 < len(slots) else 0) + (1 if i + 2 < len(slots) else 0) + (1 if strategy else 0)
                            i += consumed
                    elif slots[i] == "Call" and i + 1 < len(slots):
                        lid = slots[i + 1].lstrip("L").split(":")[-1]
                        out_var = None
                        if i + 2 < len(slots) and slots[i + 2].startswith("->") and not slots[i + 2].startswith("->L"):
                            out_var = slots[i + 2][2:]
                            i += 3
                        elif i + 2 < len(slots) and slots[i + 2] not in step_ops and self.strict_mode:
                            self._errors.append(
                                f"Line {lineno}: Call optional return binding must be -><var>, got {slots[i + 2]!r}"
                            )
                            i += 3
                        else:
                            i += 2
                        step = {"op": "Call", "lineno": lineno, "label": lid}
                        if out_var:
                            step["out"] = out_var
                        leg["steps"].append(step)
                    elif slots[i] == "X" and i + 2 < len(slots):
                        dst = slots[i + 1]
                        fn = slots[i + 2]
                        args = []
                        j = i + 3
                        while j < len(slots) and slots[j] not in step_ops:
                            args.append(slots[j])
                            j += 1
                        # Strip S-expression parentheses: the tokenizer does not treat
                        # '(' and ')' as delimiters, so "X dst (core.add 3 4)" arrives
                        # as fn="(core.add", args may end with "4)" or a standalone ")".
                        fn = fn.lstrip("(")
                        if args and isinstance(args[-1], str):
                            stripped = args[-1].rstrip(")")
                            if stripped:
                                args[-1] = stripped
                            else:
                                args.pop()
                        # If no args remain, strip trailing ')' from fn itself (e.g. "(core.now)" → "core.now")
                        if not args:
                            fn = fn.rstrip(")")
                        leg["steps"].append({"op": "X", "lineno": lineno, "dst": dst, "fn": fn, "args": args})
                        i = j
                    elif slots[i] == "ForEach" and i + 4 < len(slots):
                        # ForEach is an alias for Loop
                        ref = slots[i + 1]
                        item = slots[i + 2]
                        body = self._parse_arrow_lbl(slots[i + 3]) or slots[i + 3].lstrip("L").split(":")[-1]
                        after = self._parse_arrow_lbl(slots[i + 4]) or slots[i + 4].lstrip("L").split(":")[-1]
                        leg["steps"].append({"op": "Loop", "lineno": lineno, "ref": ref, "item": item, "body": body, "after": after})
                        i += 5
                    elif slots[i] == "Loop" and i + 4 < len(slots):
                        ref = slots[i + 1]
                        item = slots[i + 2]
                        body = self._parse_arrow_lbl(slots[i + 3]) or slots[i + 3].lstrip("L").split(":")[-1]
                        after = self._parse_arrow_lbl(slots[i + 4]) or slots[i + 4].lstrip("L").split(":")[-1]
                        leg["steps"].append({"op": "Loop", "lineno": lineno, "ref": ref, "item": item, "body": body, "after": after})
                        i += 5
                    elif slots[i] == "While" and i + 3 < len(slots):
                        cond = slots[i + 1]
                        body = self._parse_arrow_lbl(slots[i + 2]) or slots[i + 2].lstrip("L").split(":")[-1]
                        after = self._parse_arrow_lbl(slots[i + 3]) or slots[i + 3].lstrip("L").split(":")[-1]
                        step = {"op": "While", "lineno": lineno, "cond": cond, "body": body, "after": after}
                        if i + 4 < len(slots) and slots[i + 4].startswith("limit="):
                            step["limit"] = slots[i + 4].split("=", 1)[1] or "10000"
                            i += 5
                        else:
                            i += 4
                        leg["steps"].append(step)
                    elif slots[i] == "CacheGet" and i + 2 < len(slots):
                        name = slots[i + 1]
                        key = slots[i + 2]
                        out = "data"
                        fallback = None
                        j = i + 3
                        if j < len(slots) and slots[j].startswith("->") and not slots[j].startswith("->L"):
                            out = slots[j][2:]
                            j += 1
                        if j < len(slots) and slots[j] not in step_ops:
                            fallback = slots[j]
                            j += 1
                        step = {"op": "CacheGet", "lineno": lineno, "name": name, "key": key, "out": out, "fallback": fallback}
                        lit_fields = {}
                        if i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string":
                            lit_fields["key"] = True
                        if fallback is not None:
                            fb_idx = j - 1
                            if fb_idx < len(slot_kinds) and slot_kinds[fb_idx] == "string":
                                lit_fields["fallback"] = True
                        if lit_fields:
                            step["__literal_fields"] = lit_fields
                        leg["steps"].append(step)
                        i = j
                    elif slots[i] == "CacheSet" and i + 3 < len(slots):
                        name = slots[i + 1]
                        key = slots[i + 2]
                        value = slots[i + 3]
                        ttl_s = slots[i + 4] if i + 4 < len(slots) and slots[i + 4] not in step_ops else "0"
                        step = {"op": "CacheSet", "lineno": lineno, "name": name, "key": key, "value": value, "ttl_s": ttl_s}
                        lit_fields = {}
                        if i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string":
                            lit_fields["key"] = True
                        if i + 3 < len(slot_kinds) and slot_kinds[i + 3] == "string":
                            lit_fields["value"] = True
                        if lit_fields:
                            step["__literal_fields"] = lit_fields
                        leg["steps"].append(step)
                        i += 5 if (i + 4 < len(slots) and slots[i + 4] not in step_ops) else 4
                    elif slots[i] == "QueuePut" and i + 2 < len(slots):
                        queue = slots[i + 1]
                        value = slots[i + 2]
                        value_is_string = (i + 2 < len(slot_kinds) and slot_kinds[i + 2] == "string")
                        out = None
                        if i + 3 < len(slots) and slots[i + 3].startswith("->") and not slots[i + 3].startswith("->L"):
                            out = slots[i + 3][2:]
                            i += 4
                        else:
                            i += 3
                        step = {"op": "QueuePut", "lineno": lineno, "queue": queue, "value": value, "out": out}
                        if value_is_string:
                            step["__literal_fields"] = {"value": True}
                        leg["steps"].append(step)
                    elif slots[i] == "Tx" and i + 2 < len(slots):
                        leg["steps"].append({"op": "Tx", "lineno": lineno, "action": slots[i + 1], "name": slots[i + 2]})
                        i += 3
                    elif slots[i] == "Enf" and i + 1 < len(slots):
                        leg["steps"].append({"op": "Enf", "lineno": lineno, "policy": slots[i + 1]})
                        i += 2
                    else:
                        i += 1

            elif op == "R":
                parsed = self._parse_req_slots(slots)
                if self.current_label:
                    self._label_steps(self.current_label).append({"op": "R", "lineno": lineno, **parsed} if parsed else {"op": "R", "lineno": lineno, "raw": slots})
                else:
                    self._label_steps("_anon").append({"op": "R", "lineno": lineno, **(parsed or {}), "raw": slots})

            elif op == "J":
                var = slots[0] if slots else "data"
                step_j = {"op": "J", "lineno": lineno, "var": var}
                if slots and slot_kinds and slot_kinds[0] == "string":
                    step_j["__literal_fields"] = {"var": True}
                if self.current_label:
                    self._label_steps(self.current_label).append(step_j)
                else:
                    self._label_steps("_anon").append(step_j)

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
                    self.capabilities.setdefault("queue", {})[name] = {"maxSize": max_sz, "retry": retry}

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
                    self.capabilities.setdefault("cache", {})[name] = {"key": key, "ttl": ttl, "default": default}

            elif op == "Pol":
                if len(slots) >= 1:
                    name = slots[0]
                    constraints: Dict[str, Any] = {}
                    for tok in slots[1:]:
                        if "=" in tok:
                            k, v = tok.split("=", 1)
                            constraints[k] = v
                    self.services.setdefault("policy", {}).setdefault("defs", {})[name] = {"constraints": constraints, "raw": slots[1:]}
                    self.capabilities.setdefault("policy", {})[name] = {"constraints": constraints, "raw": slots[1:]}

            elif op == "Txn":
                if len(slots) >= 1:
                    name = slots[0]
                    adapter = slots[1] if len(slots) > 1 else "db"
                    mode = slots[2] if len(slots) > 2 else "readwrite"
                    self.services.setdefault("txn", {}).setdefault("defs", {})[name] = {"adapter": adapter, "mode": mode}
                    self.capabilities.setdefault("txn", {})[name] = {"adapter": adapter, "mode": mode}

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
                    self.capabilities["auth"] = {"kind": kind, "arg": arg, "extra": extra}

            # --- Core: control flow, vars, composition ---
            elif op == "If":
                if len(slots) >= 2 and self.current_label:
                    cond = slots[0]
                    then_l = self._normalize_if_target(slots[1], allow_fallback=True)
                    else_l = self._normalize_if_target(slots[2], allow_fallback=True) if len(slots) > 2 else None
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "If", "lineno": lineno, "cond": cond, "then": then_l, "else": else_l})
            elif op == "Err":
                if slots and self.current_label:
                    at_node = self._parse_at_node_id(slots[0])
                    if at_node is not None:
                        handler_slot = slots[1] if len(slots) > 1 else None
                        if not handler_slot:
                            if self.strict_mode:
                                self._errors.append(f"Line {lineno}: Err @node_id requires handler (e.g. ->L9)")
                        else:
                            handler = handler_slot[2:] if handler_slot.startswith("->") else handler_slot
                            if handler.startswith("L"):
                                handler = handler[1:]
                            if ":" in handler:
                                handler = handler.split(":")[-1]
                            self._ensure_label(self.current_label)
                            self._label_steps(self.current_label).append({"op": "Err", "lineno": lineno, "handler": handler, "at_node_id": at_node})
                    else:
                        handler = slots[0][2:] if slots[0].startswith("->") else slots[0]
                        if handler.startswith("L"):
                            handler = handler[1:]
                        if ":" in handler:
                            handler = handler.split(":")[-1]
                        self._ensure_label(self.current_label)
                        self._label_steps(self.current_label).append({"op": "Err", "lineno": lineno, "handler": handler})
            elif op == "Retry":
                if self.current_label:
                    at_node = self._parse_at_node_id(slots[0]) if slots else None
                    if at_node is not None:
                        count = slots[1] if len(slots) > 1 else "3"
                        backoff = slots[2] if len(slots) > 2 else "0"
                        strategy = slots[3] if len(slots) > 3 and slots[3] in ("fixed", "exponential") else None
                        self._ensure_label(self.current_label)
                        step_d: Dict[str, Any] = {"op": "Retry", "lineno": lineno, "count": count, "backoff_ms": backoff, "at_node_id": at_node}
                        if strategy:
                            step_d["backoff_strategy"] = strategy
                        self._label_steps(self.current_label).append(step_d)
                    else:
                        count = slots[0] if slots else "3"
                        backoff = slots[1] if len(slots) > 1 else "0"
                        strategy = slots[2] if len(slots) > 2 and slots[2] in ("fixed", "exponential") else None
                        self._ensure_label(self.current_label)
                        step_d = {"op": "Retry", "lineno": lineno, "count": count, "backoff_ms": backoff}
                        if strategy:
                            step_d["backoff_strategy"] = strategy
                        self._label_steps(self.current_label).append(step_d)
            elif op == "Call":
                if slots and self.current_label:
                    lid = slots[0]
                    if lid.startswith("L"):
                        lid = lid[1:]
                    if ":" in lid:
                        lid = lid.split(":")[-1]
                    out_var = slots[1][2:] if len(slots) > 1 and slots[1].startswith("->") and not slots[1].startswith("->L") else None
                    if len(slots) > 1 and out_var is None and self.strict_mode:
                        self._errors.append(
                            f"Line {lineno}: Call optional return binding must be -><var>, got {slots[1]!r}"
                        )
                    self._ensure_label(self.current_label)
                    step = {"op": "Call", "lineno": lineno, "label": lid}
                    if out_var:
                        step["out"] = out_var
                    self._label_steps(self.current_label).append(step)
            elif op == "Set":
                if len(slots) >= 2 and self.current_label:
                    self._ensure_label(self.current_label)
                    step = {"op": "Set", "lineno": lineno, "name": slots[0], "ref": slots[1]}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        step["__literal_fields"] = {"ref": True}
                    self._label_steps(self.current_label).append(step)
            elif op == "Filt":
                if len(slots) >= 5 and self.current_label:
                    self._ensure_label(self.current_label)
                    step = {"op": "Filt", "lineno": lineno, "name": slots[0], "ref": slots[1], "field": slots[2], "cmp": slots[3], "value": slots[4]}
                    lit_fields = {}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        lit_fields["ref"] = True
                    if len(slot_kinds) > 4 and slot_kinds[4] == "string":
                        lit_fields["value"] = True
                    if lit_fields:
                        step["__literal_fields"] = lit_fields
                    self._label_steps(self.current_label).append(step)
            elif op == "Sort":
                if len(slots) >= 3 and self.current_label:
                    order = slots[3] if len(slots) > 3 else "asc"
                    self._ensure_label(self.current_label)
                    step = {"op": "Sort", "lineno": lineno, "name": slots[0], "ref": slots[1], "field": slots[2], "order": order}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        step["__literal_fields"] = {"ref": True}
                    self._label_steps(self.current_label).append(step)
            elif op == "X":
                if len(slots) >= 2 and self.current_label:
                    self._ensure_label(self.current_label)
                    # Strip S-expression parentheses: "X dst (core.add 3 4)" tokenizes as
                    # fn="(core.add", last-arg may be "4)" or a standalone ")".
                    # '(' and ')' are not token delimiters so they attach to adjacent tokens.
                    x_fn = slots[1].lstrip("(")
                    x_args = list(slots[2:])
                    if x_args and isinstance(x_args[-1], str):
                        stripped = x_args[-1].rstrip(")")
                        if stripped:
                            x_args[-1] = stripped
                        else:
                            x_args.pop()
                    # If no args remain, strip trailing ')' from fn itself (e.g. "(core.now)" → "core.now")
                    if not x_args:
                        x_fn = x_fn.rstrip(")")
                    self._label_steps(self.current_label).append({"op": "X", "lineno": lineno, "dst": slots[0], "fn": x_fn, "args": x_args})
            elif op == "Loop":
                if len(slots) >= 4 and self.current_label:
                    body = self._parse_arrow_lbl(slots[2]) or slots[2].lstrip("L").split(":")[-1]
                    after = self._parse_arrow_lbl(slots[3]) or slots[3].lstrip("L").split(":")[-1]
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Loop", "lineno": lineno, "ref": slots[0], "item": slots[1], "body": body, "after": after})
            elif op == "While":
                if len(slots) >= 3 and self.current_label:
                    body = self._parse_arrow_lbl(slots[1]) or slots[1].lstrip("L").split(":")[-1]
                    after = self._parse_arrow_lbl(slots[2]) or slots[2].lstrip("L").split(":")[-1]
                    limit = None
                    if len(slots) > 3 and slots[3].startswith("limit="):
                        limit = slots[3].split("=", 1)[1] or "10000"
                    self._ensure_label(self.current_label)
                    step = {"op": "While", "lineno": lineno, "cond": slots[0], "body": body, "after": after}
                    if limit is not None:
                        step["limit"] = limit
                    self._label_steps(self.current_label).append(step)
            elif op == "CacheGet":
                if len(slots) >= 2 and self.current_label:
                    out = "data"
                    fallback = None
                    idx = 2
                    if len(slots) > idx and slots[idx].startswith("->") and not slots[idx].startswith("->L"):
                        out = slots[idx][2:]
                        idx += 1
                    if len(slots) > idx:
                        fallback = slots[idx]
                    self._ensure_label(self.current_label)
                    step = {"op": "CacheGet", "lineno": lineno, "name": slots[0], "key": slots[1], "out": out, "fallback": fallback}
                    lit_fields = {}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        lit_fields["key"] = True
                    if fallback is not None and len(slot_kinds) > idx and slot_kinds[idx] == "string":
                        lit_fields["fallback"] = True
                    if lit_fields:
                        step["__literal_fields"] = lit_fields
                    self._label_steps(self.current_label).append(step)
            elif op == "CacheSet":
                if len(slots) >= 3 and self.current_label:
                    ttl_s = slots[3] if len(slots) > 3 else "0"
                    self._ensure_label(self.current_label)
                    step = {"op": "CacheSet", "lineno": lineno, "name": slots[0], "key": slots[1], "value": slots[2], "ttl_s": ttl_s}
                    lit_fields = {}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        lit_fields["key"] = True
                    if len(slot_kinds) > 2 and slot_kinds[2] == "string":
                        lit_fields["value"] = True
                    if lit_fields:
                        step["__literal_fields"] = lit_fields
                    self._label_steps(self.current_label).append(step)
            elif op == "QueuePut":
                if len(slots) >= 2 and self.current_label:
                    out = slots[2][2:] if len(slots) > 2 and slots[2].startswith("->") and not slots[2].startswith("->L") else None
                    self._ensure_label(self.current_label)
                    step = {"op": "QueuePut", "lineno": lineno, "queue": slots[0], "value": slots[1], "out": out}
                    if len(slot_kinds) > 1 and slot_kinds[1] == "string":
                        step["__literal_fields"] = {"value": True}
                    self._label_steps(self.current_label).append(step)
            elif op == "Tx":
                if len(slots) >= 2 and self.current_label:
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Tx", "lineno": lineno, "action": slots[0], "name": slots[1]})
            elif op == "Enf":
                if slots and self.current_label:
                    self._ensure_label(self.current_label)
                    self._label_steps(self.current_label).append({"op": "Enf", "lineno": lineno, "policy": slots[0]})
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
                if self.strict_mode and mod and mop and mod in KNOWN_MODULES:
                    self._errors.append(
                        f"Line {lineno}: unknown module.op {op!r} in strict mode"
                    )
                self.meta.append(self._meta_record(lineno, line_node))

        if emit_graph:
            self._steps_to_graph_all()
            normalize_labels(self.labels)
            annotate_labels_effect_analysis(self.labels)

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
                    msg = f"Endpoint {path} {method}: label {label_id!r} does not exist"
                    self._errors.append(msg)
                    if context is not None:
                        ep_row = self._strict_endpoint_line_node(path, method, cst_lines)
                        e_lineno = int(ep_row.get("lineno") or 1) if ep_row else 1
                        if ep_row:
                            span_e, col_e = self._strict_nth_slot_content_char_span(
                                ep_row, 2, e_lineno, source_lines
                            )
                        else:
                            span_e, col_e = None, 1
                        closest = self._strict_closest_label_id(label_id)
                        related = (
                            self._strict_label_decl_line_char_span(closest, cst_lines, source_lines)
                            if closest
                            else None
                        )
                        fix = (
                            "Declare the missing L"
                            f"{label_id}: block, or change the endpoint target to an existing label."
                        )
                        if closest:
                            fix += f" Did you mean L{closest}?"
                        # Phase 2: native structured diagnostic + legacy string (undeclared endpoint label).
                        context.diagnostics.append(
                            Diagnostic(
                                lineno=e_lineno,
                                col_offset=col_e,
                                kind="undeclared_reference",
                                message=msg,
                                span=span_e,
                                label_id=label_id,
                                node_id=None,
                                contract_violation_reason="Endpoint handler label is not defined in this program.",
                                suggested_fix=fix,
                                related_span=related,
                            )
                        )
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
                    elif opn == "Loop":
                        for x in (s.get("body"), s.get("after")):
                            lx = self._norm_lid(x)
                            if lx:
                                targeted_labels.add(lx)
                    elif opn == "While":
                        for x in (s.get("body"), s.get("after")):
                            lx = self._norm_lid(x)
                            if lx:
                                targeted_labels.add(lx)

            # Every targeted label should exist, have legacy.steps, and end with exactly one J.
            for tl in sorted(targeted_labels):
                body = self.labels.get(tl)
                if not body:
                    msg = f"Targeted label {tl!r} does not exist"
                    self._errors.append(msg)
                    if context is not None:
                        ref_ln = self._strict_first_step_ref_lineno(tl)
                        u_lineno = ref_ln if ref_ln is not None else 1
                        closest = self._strict_closest_label_id(tl)
                        related = (
                            self._strict_label_decl_line_char_span(closest, cst_lines, source_lines)
                            if closest
                            else None
                        )
                        fix = (
                            "Declare the missing L"
                            f"{tl}: block, or change the control-flow target to an existing label."
                        )
                        if closest:
                            fix += f" Did you mean L{closest}?"
                        # Phase 2: native structured diagnostic + legacy string (undeclared targeted label).
                        context.diagnostics.append(
                            Diagnostic(
                                lineno=u_lineno,
                                col_offset=1,
                                kind="undeclared_reference",
                                message=msg,
                                span=None,
                                label_id=tl,
                                node_id=None,
                                contract_violation_reason=(
                                    "A control-flow step references a label that is not defined."
                                ),
                                suggested_fix=fix,
                                related_span=related,
                            )
                        )
                    continue
                steps = body.get("legacy", {}).get("steps", [])
                if not steps:
                    self._errors.append(f"Targeted label {tl!r} has no legacy.steps")
                    continue
                j_steps = [s for s in steps if s.get("op") == "J"]
                # If as last step: then/else targets must each end with exactly one J (checked separately).
                if steps and steps[-1].get("op") == "If":
                    continue
                if len(j_steps) != 1:
                    self._errors.append(f"Targeted label {tl!r} must contain exactly one J (has {len(j_steps)})")
                    continue
                if steps[-1].get("op") != "J":
                    self._errors.append(f"Targeted label {tl!r} must end in J")

            # Core-only label enforcement: every step op must be in STEP_OPS (spec §3.5).
            for lid, body in self.labels.items():
                for idx, s in enumerate(body.get("legacy", {}).get("steps", [])):
                    opn = s.get("op")
                    if opn and opn not in self.STEP_OPS:
                        self._errors.append(
                            f"Label {lid!r}: step at index {idx} has op {opn!r} not in core ops (strict core-only)"
                        )

            # Capability reference validation in label steps.
            cache_defs = set((self.services.get("cache", {}).get("defs", {}) or {}).keys())
            queue_defs = set((self.services.get("queue", {}).get("defs", {}) or {}).keys())
            txn_defs = set((self.services.get("txn", {}).get("defs", {}) or {}).keys())
            policy_defs = set((self.services.get("policy", {}).get("defs", {}) or {}).keys())
            for lid, body in self.labels.items():
                for s in body.get("legacy", {}).get("steps", []):
                    opn = s.get("op")
                    if opn in ("CacheGet", "CacheSet"):
                        name = s.get("name", "")
                        if name and name not in cache_defs:
                            self._errors.append(f"Label {lid!r}: {opn} references undefined cache {name!r}")
                    elif opn == "QueuePut":
                        qn = s.get("queue", "")
                        if qn and qn not in queue_defs:
                            self._errors.append(f"Label {lid!r}: QueuePut references undefined queue {qn!r}")
                    elif opn == "Tx":
                        tn = s.get("name", "")
                        if tn and tn not in txn_defs:
                            self._errors.append(f"Label {lid!r}: Tx references undefined transaction {tn!r}")
                    elif opn == "Enf":
                        pn = s.get("policy", "")
                        if pn and pn not in policy_defs:
                            self._errors.append(f"Label {lid!r}: Enf references undefined policy {pn!r}")

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
                        elif s.get("op") == "Loop":
                            for x in (s.get("body"), s.get("after")):
                                nx = self._norm_lid(x)
                                if nx:
                                    nxt.add(nx)
                        elif s.get("op") == "While":
                            for x in (s.get("body"), s.get("after")):
                                nx = self._norm_lid(x)
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

            # Graph-level invariants on nodes/edges/entry/exits (canonical graph IR).
            self._validate_graphs()

        if self.meta:
            self._warnings.append(f"meta contains {len(self.meta)} preserved unknown/invalid lines")
        if self.api_opts.get("deprecate"):
            self._warnings.append(f"api deprecations declared: {len(self.api_opts.get('deprecate', []))}")
        self._append_canonical_lint_warnings(cst_lines)

        # Internal compile-time hints (__literal_fields on legacy steps) must stay on self.labels
        # until the final IR is built: included subgraphs are merged into the parent compiler
        # and _steps_to_graph_all() re-lowers steps → nodes; without hints, J "ok" becomes a read
        # of ok. Strip only on the deepcopy attached to the returned IR.

        # Add fuzzy suggestions to errors before returning IR
        self._augment_errors_with_suggestions()

        if context is not None:
            # Phase 2–3: merge native diagnostics (rich spans/suggestions) with string-derived
            # rows from legacy _errors, then dedupe so natives win for the same issue.
            native_snapshot = list(context.diagnostics)
            context.replace_from_error_strings(self._errors)
            # Phase 3: natives first → prefer rows with span/suggested_fix/label_id; drop
            # duplicate string-merge rows. Key is (kind, body) with "Line N:" stripped from
            # message so native + error_strings_to_diagnostics match; lineno is omitted
            # because legacy parsing defaults to line 1 when the error string has no prefix.
            seen_keys: Set[Tuple[str, str]] = set()
            deduped: List[Diagnostic] = []
            for d in native_snapshot + context.diagnostics:
                raw_msg = str(d.message or "")
                lm = re.match(r"^Line\s+\d+:\s*", raw_msg, re.IGNORECASE)
                body = raw_msg[lm.end() :].strip() if lm else raw_msg.strip()
                key = (str(d.kind), body)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(d)
            context.diagnostics.clear()
            context.diagnostics.extend(deduped)
            self._enrich_structured_diagnostics(context)

        if context is not None and context.should_raise_after_compile(
            strict_mode=self.strict_mode,
            legacy_errors=self._errors,
        ):
            raise CompilationDiagnosticError(list(context.diagnostics), source_text)

        labels_for_ir = copy.deepcopy(self.labels)
        for _lid, _body in labels_for_ir.items():
            _steps = ((_body.get("legacy") or {}).get("steps") or [])
            for _s in _steps:
                if isinstance(_s, dict):
                    _s.pop("__literal_fields", None)

        ir: Dict[str, Any] = {
            "ir_version": self.ver or "1.0.0",
            "graph_schema_version": "1.0",
            "source": {"text": source_text, "lines": source_lines},
            "cst": {"lines": cst_lines},
            "services": self.services,
            "types": self.types,
            "labels": labels_for_ir,
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
            "capabilities": self.capabilities,
            "emit_capabilities": self._compute_emit_capabilities(),
            "runtime_policy": {"execution_mode": "graph-preferred", "unknown_op_policy": "skip"},
            "meta": self.meta,
            "errors": self._errors,
            "warnings": self._warnings,
            "diagnostics": self._build_structured_diagnostics(self.labels, cst_lines),
            "stats": {
                "lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
                "ops": parsed_ops,
            },
        }
        if context is not None:
            ir["structured_diagnostics"] = [d.to_dict() for d in context.diagnostics]
        ir["required_emit_targets"] = self._compute_required_emit_targets(ir["emit_capabilities"])
        _req = ir["required_emit_targets"]
        _req["minimal_emit"] = apply_minimal_emit_python_api_stub_fallback(
            ir=ir, targets=_req["minimal_emit"]
        )
        # Attach semantic hashes and graph checksum without changing semantics.
        ir = attach_label_and_node_hashes(ir)
        ir["graph_semantic_checksum"] = graph_semantic_checksum(ir)
        return ir

    def emit_source_exact(self, ir: Dict[str, Any]) -> str:
        """Return the stored original source text (byte-for-byte), not reconstructed."""
        src = ir.get("source") or {}
        return src.get("text", "")

    def _provenance_identity(self) -> Dict[str, Any]:
        return {
            "project": "AINL",
            "full_name": "AI Native Lang",
            "initiator": "Steven Hooley",
            "x": "https://x.com/sbhooley",
            "website": "https://stevenhooley.com",
            "linkedin": "https://linkedin.com/in/sbhooley",
            "repo_doc": "docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md",
            "machine_doc": "tooling/project_provenance.json",
        }

    def _emit_provenance_comment_block(self, comment_prefix: str, emitted_label: str) -> str:
        p = self._provenance_identity()
        lines = [
            f"{comment_prefix} {emitted_label}",
            f"{comment_prefix} Source project: {p['full_name']} ({p['project']})",
            f"{comment_prefix} Human initiator: {p['initiator']}",
            f"{comment_prefix} Public references: {p['x']} | {p['website']} | {p['linkedin']}",
            f"{comment_prefix} Provenance docs: {p['repo_doc']} | {p['machine_doc']}",
        ]
        return "\n".join(lines) + "\n"

    def _openapi_provenance(self) -> Dict[str, Any]:
        p = self._provenance_identity()
        return {
            "project": p["full_name"],
            "initiator": p["initiator"],
            "public_references": {
                "x": p["x"],
                "website": p["website"],
                "linkedin": p["linkedin"],
            },
            "provenance_docs": {
                "repo": p["repo_doc"],
                "machine": p["machine_doc"],
            },
        }

    def emit_react(self, ir: Dict[str, Any]) -> str:
        # Compact version — reduced react_ts emit from ~480 toward ~320–380 aggregate-profile chunks (tiktoken cl100k_base)
        # Original boilerplate trimmed for benchmark efficiency without functional change
        fe = ir["services"].get("fe", {})
        uis = fe.get("ui", {})
        states = fe.get("states", {})
        _who = self._provenance_identity()["initiator"]
        jsx = f"// AINL React/TSX (AI Native Lang; {_who})\nimport React,{{useState}}from'react';\n"
        for ui_name, props in uis.items():
            state_list = states.get(ui_name, [("data", "any")])
            jsx += f"export const {ui_name}=()=>{{\n"
            for var, typ in state_list:
                ts_typ = normalize_type(typ)
                setter = "set" + (var[:1].upper() + var[1:] if var else "Data")
                default = default_value_for_type(ts_typ)
                jsx += f"const[{var},{setter}]=useState<{ts_typ}>({default});\n"
            jsx += f"return <div className=\"dashboard\"><h1>{ui_name}</h1>"
            if props:
                comp = props[0]
                data_prop = props[1] if len(props) > 1 else (props[0] if props[0].islower() or not props[0][:1].isupper() else "data")
                if comp[0].islower():
                    comp = "DataTable"
                    data_prop = props[0]
                jsx += f"<{comp} data={{{data_prop}}}/>"
            jsx += "</div>;\n};\n"
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

        jsx = self._emit_provenance_comment_block("//", "AINL emitted browser React app")
        jsx += "const { useState, useEffect } = React;\n\n"
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
        # Compact version — reduced prisma emit from ~1116 toward ~700–800 aggregate-profile chunks (tiktoken cl100k_base)
        # Original boilerplate trimmed for benchmark efficiency without functional change
        _who = self._provenance_identity()["initiator"]
        out = (
            f"// AINL Prisma (AI Native Lang; {_who})\n"
            'generator client{provider="prisma-client-js"}\n'
            'datasource db{provider="postgresql" url=env("DATABASE_URL")}\n'
        )
        for name, data in ir["types"].items():
            out += f"model {name}{{\n"
            fields = data.get("fields", {})
            if "id" not in fields and "id:I" not in str(fields):
                out += "  id Int @id @default(autoincrement())\n"
            for fname, typ in fields.items():
                prisma_typ = normalize_type(typ)
                out += f"  {fname} {prisma_typ}\n"
            out += "}\n"
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

    def _safe_py_ident(self, s: str, fallback: str = "fn") -> str:
        """Convert arbitrary text into a safe Python identifier."""
        base = re.sub(r"[^A-Za-z0-9_]", "_", (s or "").strip())
        if not base:
            base = fallback
        if base[0].isdigit():
            base = "_" + base
        return base

    def emit_python_api(self, ir: Dict[str, Any]) -> str:
        # Minimal Python API fallback for minimal_emit: ensures every artifact emits at least a runnable stub
        # Prevents 0-chunk outputs in legacy/public profiles without required targets
        if ir.get("emit_python_api_fallback_stub"):
            return (
                "import asyncio\n\n"
                "async def main():\n"
                '    print("AINL minimal fallback stub - no specific targets required")\n\n'
                'if __name__ == "__main__":\n'
                "    asyncio.run(main())\n"
            )
        py = self._emit_provenance_comment_block("#", "AINL emitted FastAPI stub")
        py += "from fastapi import FastAPI\napp = FastAPI()\n\n"
        idx = 0
        for srv, data in ir["services"].items():
            if "eps" not in data:
                continue
            for path, method, ep in _iter_eps(data["eps"]):
                meth = self._http_method(method or ep.get("method", "G"))
                py += f"@app.{meth}('{path}')\n"
                py += f"def e{idx}():return{{}}\n\n"
                idx += 1
        return py

    def emit_mt5(self, ir: Dict[str, Any]) -> str:
        code = self._emit_provenance_comment_block("//", "AINL emitted MT5 Expert Advisor stub")
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
            return self._emit_provenance_comment_block("#", "AINL emitted scraper stub") + "import requests\n"
        code = self._emit_provenance_comment_block("#", "AINL emitted scraper")
        code += "import requests\nfrom bs4 import BeautifulSoup as B\n\n"
        for name, defn in defs.items():
            url = defn.get("url", "")
            selectors = defn.get("selectors", {})
            code += f"def scrape_{name}():\n"
            code += f"    s=B(requests.get('{url}').text,'html.parser')\n"
            code += "    f=lambda q:(e.get_text(strip=True)if(e:=s.select_one(q))else None)\n"
            fields = ",".join([f"'{v}':f('{css}')" for v, css in selectors.items()])
            code += f"    return{{{fields}}}\n\n"
        return code

    def emit_cron_stub(self, ir: Dict[str, Any]) -> str:
        crons = ir.get("crons", [])
        if not crons:
            return ""
        py = self._emit_provenance_comment_block("#", "AINL emitted cron stub")
        for c in crons:
            py += f"def run_{c['label']}():\n"
            py += f"    # {c['expr']}\n"
            py += "    pass\n\n"
        return py

    def emit_hyperspace_agent(self, ir: Dict[str, Any], *, source_stem: str = "ainl_graph") -> str:
        """Emit standalone hyperspace_agent.py: embedded IR, RuntimeEngine, Phase-3 adapters, optional SDK stub."""
        import base64
        import json as _json

        ir_blob = base64.standard_b64encode(_json.dumps(ir, ensure_ascii=False).encode("utf-8")).decode("ascii")
        stem = str(source_stem or "ainl_graph").replace("\\", "/").split("/")[-1]

        py = '"""Standalone AINL runtime wrapper with optional Hyperspace SDK integration stub."""\n'
        py += self._emit_provenance_comment_block("#", "AINL emitted Hyperspace agent wrapper")
        py += "import base64\nimport json\nimport logging\nimport os\nimport sys\nimport warnings\nfrom pathlib import Path\n\n"
        py += "_log = logging.getLogger(__name__)\n\n"
        py += "try:\n"
        py += "    import hyperspace_sdk  # type: ignore\n"
        py += "    _HYPERSPACE_SDK = True\n"
        py += "except ImportError:\n"
        py += "    hyperspace_sdk = None  # type: ignore\n"
        py += "    _HYPERSPACE_SDK = False\n"
        py += "    warnings.warn(\n"
        py += (
            '        "hyperspace_sdk not installed; running AINL RuntimeEngine only '
            '(install the official SDK when available).",\n'
        )
        py += "        RuntimeWarning,\n"
        py += "        stacklevel=2,\n"
        py += "    )\n\n"
        py += "_IR_B64 = " + repr(ir_blob) + "\n"
        py += "_SOURCE_STEM = " + repr(stem) + "\n\n"

        py += "def _repo_root() -> Path:\n"
        py += "    _here = Path(__file__).resolve().parent\n"
        py += "    for start in (_here, Path.cwd().resolve()):\n"
        py += "        root = start\n"
        py += "        for _ in range(14):\n"
        py += "            if (root / \"runtime\" / \"engine.py\").is_file() and (root / \"adapters\").is_dir():\n"
        py += "                return root\n"
        py += "            if root.parent == root:\n"
        py += "                break\n"
        py += "            root = root.parent\n"
        py += "    return _here\n\n"

        py += "_ROOT = _repo_root()\n"
        py += "if str(_ROOT) not in sys.path:\n"
        py += "    sys.path.insert(0, str(_ROOT))\n\n"

        py += "from runtime.engine import RuntimeEngine\n"
        py += "from runtime.adapters.base import AdapterRegistry\n"
        py += "from adapters.vector_memory import VectorMemoryAdapter\n"
        py += "from adapters.tool_registry import ToolRegistryAdapter\n\n"

        py += "def build_registry() -> AdapterRegistry:\n"
        py += (
            "    reg = AdapterRegistry(allowed=[\"core\", \"vector_memory\", \"tool_registry\"])\n"
        )
        py += "    reg.register(\"vector_memory\", VectorMemoryAdapter())\n"
        py += "    reg.register(\"tool_registry\", ToolRegistryAdapter())\n"
        py += "    return reg\n\n"

        py += "def trajectory_log_path_from_env():\n"
        py += "    v = os.environ.get(\"AINL_LOG_TRAJECTORY\", \"\").strip().lower()\n"
        py += "    if v in (\"1\", \"true\", \"yes\", \"on\"):\n"
        py += "        return str(Path.cwd() / f\"{_SOURCE_STEM}.trajectory.jsonl\")\n"
        py += "    return None\n\n"

        py += "def make_engine(registry: AdapterRegistry, trajectory_log_path):\n"
        py += "    _ir = json.loads(base64.standard_b64decode(_IR_B64))\n"
        py += "    return RuntimeEngine(\n"
        py += "        ir=_ir,\n"
        py += "        adapters=registry,\n"
        py += "        trace=False,\n"
        py += "        step_fallback=True,\n"
        py += "        execution_mode=\"graph-preferred\",\n"
        py += "        trajectory_log_path=trajectory_log_path,\n"
        py += "    )\n\n"

        py += "def run_ainl(label=None, frame=None):\n"
        py += "    reg = build_registry()\n"
        py += "    traj = trajectory_log_path_from_env()\n"
        py += "    if traj:\n"
        py += "        _log.info(\"AINL trajectory logging -> %s\", traj)\n"
        py += "    eng = make_engine(reg, traj)\n"
        py += "    lid = label if label is not None else eng.default_entry_label()\n"
        py += "    return eng.run_label(lid, frame=frame if frame is not None else {})\n\n"

        py += 'if __name__ == "__main__":\n'
        py += "    logging.basicConfig(level=logging.INFO, format=\"%(levelname)s %(message)s\")\n"
        py += "    if _HYPERSPACE_SDK:\n"
        py += "        # TODO: integrate with hyperspace_sdk (Agent/Session, register run_ainl as callback,\n"
        py += "        # tool discovery via tool_registry.LIST / DISCOVER, session-scoped trajectory).\n"
        py += "        _log.info(\"Hyperspace SDK present; native bridge not yet wired — executing graph directly.\")\n"
        py += "    result = run_ainl()\n"
        py += "    print(result)\n"

        return py

    def emit_server(self, ir: Dict[str, Any]) -> str:
        """Emit server that runs labels via RuntimeEngine + pluggable adapters."""
        core = ir["services"].get("core", {})
        api_prefix = (core.get("path") or "/api").strip("/") or "api"
        api_prefix = "/" + api_prefix

        py = '"""Web server from AI-Native Lang: real runtime (R/P/Sc via adapters) + static + logging + rate limit."""\n'
        py += self._emit_provenance_comment_block("#", "AINL emitted runtime-backed web server")
        py += "import json\nimport sys\nimport time\nimport uuid\nimport os\nfrom pathlib import Path\nfrom collections import defaultdict\n\n"
        py += "# Allow importing runtime + adapters (same dir in Docker, else repo root)\n"
        py += "_dir = Path(__file__).resolve().parent\n"
        py += "_root = _dir\n"
        py += "for _ in range(6):\n"
        py += "    if (_root / 'runtime.py').exists() and (_root / 'adapters').exists():\n"
        py += "        break\n"
        py += "    _root = _root.parent\n"
        py += "if str(_root) not in sys.path:\n    sys.path.insert(0, str(_root))\n\n"
        py += "from fastapi import FastAPI, Request\nfrom fastapi.middleware.cors import CORSMiddleware\n"
        py += "from fastapi.staticfiles import StaticFiles\nfrom starlette.middleware.base import BaseHTTPMiddleware\nfrom starlette.responses import FileResponse\n\n"
        py += "from runtime.engine import RuntimeEngine\nfrom adapters.mock import mock_registry\n\n"
        py += "# Load IR (emitted with server); use real adapters by replacing mock_registry\n"
        py += "_ir_path = Path(__file__).resolve().parent / \"ir.json\"\n"
        py += "with open(_ir_path) as f:\n    _ir = json.load(f)\n"
        py += "_registry = mock_registry(_ir.get(\"types\"))\n"
        py += "_engine = RuntimeEngine(ir=_ir, adapters=_registry, trace=False, step_fallback=True, execution_mode='graph-preferred')\n\n"
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
        py += "def _run_label(lid, request: Request):\n"
        py += "    ctx = {\n"
        py += "        \"_role\": request.headers.get(\"X-Role\"),\n"
        py += "        \"_auth_header\": request.headers.get(\"Authorization\") or request.headers.get(\"X-Auth\"),\n"
        py += "        \"_auth_present\": bool(request.headers.get(\"Authorization\") or request.headers.get(\"X-Auth\")),\n"
        py += "    }\n"
        py += "    r = _engine.run_label(lid, frame=ctx)\n"
        py += "    return {\"data\": r if r is not None else []}\n\n"
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
                seg = self._safe_py_ident(path.strip("/").replace("/", "_"), fallback="root")
                fn_name = f"{meth}_{seg}"
                py += f"@api.{meth}('{path}'{dep_str})\n"
                py += f"def {fn_name}(request: Request):\n"
                py += f"    return _run_label('{label_id}', request)\n\n"

        py += "@api.get(\"/health\")\n"
        py += "def health():\n"
        py += "    return {\"status\": \"ok\"}\n\n"
        py += "@api.get(\"/ready\")\n"
        py += "def ready():\n"
        py += "    return {\"ready\": True}\n\n"

        py += f"app.mount(\"{api_prefix}\", api)\n\n"
        py += "# Static: serve index.html at / when present; else simple API-only landing\n"
        py += "static_dir = Path(__file__).resolve().parent / \"static\"\n"
        py += "static_dir.mkdir(exist_ok=True)\n"
        py += "_index_html = static_dir / \"index.html\" if static_dir.exists() else None\n"
        py += "if _index_html and _index_html.is_file():\n"
        py += "    @app.get(\"/\")\n"
        py += "    def _serve_index():\n"
        py += "        return FileResponse(_index_html)\n"
        py += "else:\n"
        py += "    @app.get(\"/\")\n"
        py += "    def _root():\n"
        py += "        from starlette.responses import HTMLResponse\n"
        py += "        return HTMLResponse(\"<html><body><h1>API</h1><p><a href=\\\"/api\\\">/api</a></p></body></html>\")\n"
        py += "if static_dir.exists():\n"
        py += "    app.mount(\"/\", StaticFiles(directory=str(static_dir), html=True), name=\"static\")\n\n"
        py += "if __name__ == \"__main__\":\n"
        py += "    import uvicorn\n"
        py += "    uvicorn.run(app, host=\"0.0.0.0\", port=int(os.environ.get(\"PORT\", \"8765\")))\n"
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
        if s == "B":
            return "boolean"
        if s in ("F", "S", "s", "D"):
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
        if s == "D":
            return {"type": "string", "format": "date-time"}
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
            "info": {
                "title": "AINL API",
                "version": "1.0.0",
                "x-ainl-provenance": self._openapi_provenance(),
            },
            "paths": paths,
            "components": {"schemas": schemas},
        }
        auth = ir.get("services", {}).get("auth")
        if auth:
            hdr = auth.get("arg", "Authorization")
            doc["components"].setdefault("securitySchemes", {})
            doc["components"]["securitySchemes"]["HeaderAuth"] = {"type": "apiKey", "in": "header", "name": hdr}
            doc["security"] = [{"HeaderAuth": []}]
        return json.dumps(doc, indent=2)

    def emit_dockerfile(self, ir: Dict[str, Any]) -> str:
        """Emit Dockerfile for the AINL server. Run from server dir: docker compose up --build"""
        return self._emit_provenance_comment_block("#", "AINL emitted Dockerfile") + """# AINL emitted server (build from server dir: docker compose up --build)
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
        yml = self._emit_provenance_comment_block("#", "AINL emitted docker-compose stack") + """# AINL emitted stack
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
        yml = self._emit_provenance_comment_block("#", "AINL emitted Kubernetes manifest")
        yml += f"""# AINL emitted K8s (apply: kubectl apply -f -)
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
                content = self._emit_provenance_comment_block("//", f"AINL emitted Next.js API route: {meth.upper()} {path}") + f"""import type {{ NextApiRequest, NextApiResponse }} from 'next';

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
        out["pages/api/health.ts"] = self._emit_provenance_comment_block("//", "AINL emitted Next.js health route") + """import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(_req: NextApiRequest, res: NextApiResponse) {
  res.status(200).json({ status: 'ok' });
}
"""
        out["pages/api/ready.ts"] = self._emit_provenance_comment_block("//", "AINL emitted Next.js readiness route") + """import type { NextApiRequest, NextApiResponse } from 'next';
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
            "<!-- AINL emitted Vue app -->",
            "<!-- Human initiator: Steven Hooley | https://x.com/sbhooley | https://stevenhooley.com | https://linkedin.com/in/sbhooley -->",
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
            "<!-- AINL emitted Svelte app -->",
            "<!-- Human initiator: Steven Hooley | https://x.com/sbhooley | https://stevenhooley.com | https://linkedin.com/in/sbhooley -->",
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
        lines = self._emit_provenance_comment_block("--", "AINL emitted SQL migration").splitlines()
        lines += [f"-- dialect: {dialect}", ""]
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
        lines = self._emit_provenance_comment_block("#", "AINL emitted env file").splitlines()
        lines += ["# AINL emitted env (copy to .env)", ""]
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
        lines = [
            "# Runbooks",
            "",
            "> Emitted from AINL (AI Native Lang). Human initiator: Steven Hooley.",
            "> References: <https://x.com/sbhooley> | <https://stevenhooley.com> | <https://linkedin.com/in/sbhooley>",
            "",
        ]
        for name, steps in ir.get("runbooks", {}).items():
            lines.append(f"## {name}")
            lines.append("")
            for i, step in enumerate(steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        return "\n".join(lines) if ir.get("runbooks") else "# Runbooks\n\n> Emitted from AINL (AI Native Lang). Human initiator: Steven Hooley.\n\n(No runbooks defined.)\n"

    def emit_rag_pipeline(self, ir: Dict[str, Any]) -> str:
        """Emit Python RAG pipeline: individual pieces (chunk, embed, index, retrieve, augment, generate) + full pipeline from rag.Pipe."""
        r = ir.get("rag", {})
        if not r:
            return "# AINL RAG emit\n# No rag.* ops in spec.\n"
        lines = [
            "# AINL emitted RAG pipeline (from rag.* ops)",
            "# Human initiator: Steven Hooley",
            "# Public references: https://x.com/sbhooley | https://stevenhooley.com | https://linkedin.com/in/sbhooley",
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
