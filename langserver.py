#!/usr/bin/env python3
"""
AINL Language Server (LSP) — compiler-owned grammar consumer.

This server is intentionally thin:
- formal prefix state + admissibility come from compiler-owned grammar stack
  (`compiler_grammar.py` + `grammar_constraint.py`)
- non-authoritative priors are used as UX hints only (`grammar_priors.py`)
- adapter registry enriches suggestions only when grammar says suggestions are admissible

Maintainer note:
- The compiler is the source of truth for semantics and diagnostics.
- Langserver presents compiler diagnostics; it must not invent semantics or
  claim precise locations the compiler did not provide.
- Heuristic paths (`_line_from_message`, `_find_first_line_for_op`) exist only
  for backward compatibility with older/unstructured diagnostic payloads.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from compiler_diagnostics import (
    CompilationDiagnosticError,
    CompilerContext,
    Diagnostic as StructuredDiagnostic,
)
from compiler_grammar import formal_next_token_classes, parse_prefix_state
from compiler_v2 import (
    AICodeCompiler,
    KNOWN_MODULES,
    MODULE_ALIASES,
    OP_REGISTRY,
    grammar_active_label_scope,
    grammar_apply_candidate_to_prefix,
    grammar_is_label_decl,
)
from grammar_constraint import next_token_mask, next_token_priors
from grammar_priors import sample_tokens_for_classes

try:
    from pygls.server import LanguageServer
    from pygls.workspace import Document
    from lsprotocol.types import (
        CompletionItem,
        CompletionItemKind,
        CompletionList,
        CompletionParams,
        Diagnostic,
        DiagnosticSeverity,
        Hover,
        HoverParams,
        InitializeParams,
        InitializeResult,
        InitializeResultServerInfo,
        MarkupContent,
        Position,
        Range,
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_DID_CHANGE,
        TEXT_DOCUMENT_DID_OPEN,
        TEXT_DOCUMENT_HOVER,
    )

    HAS_PYGLS = True
except Exception:
    HAS_PYGLS = False
    from dataclasses import dataclass

    LanguageServer = None  # type: ignore[assignment]
    Document = Any  # type: ignore[assignment]
    CompletionParams = Any  # type: ignore[assignment]
    HoverParams = Any  # type: ignore[assignment]
    InitializeParams = Any  # type: ignore[assignment]
    InitializeResult = Any  # type: ignore[assignment]
    InitializeResultServerInfo = Any  # type: ignore[assignment]

    @dataclass
    class Position:  # type: ignore[override]
        line: int
        character: int

    @dataclass
    class Range:  # type: ignore[override]
        start: Position
        end: Position

    class DiagnosticSeverity:  # type: ignore[override]
        Error = 1
        Warning = 2

    @dataclass
    class Diagnostic:  # type: ignore[override]
        range: Range
        message: str
        severity: int
        source: str = "ainl-compiler"
        code: Optional[str] = None

    @dataclass
    class CompletionItem:  # type: ignore[override]
        label: str
        kind: int = 1
        documentation: Optional[str] = None

    @dataclass
    class CompletionList:  # type: ignore[override]
        is_incomplete: bool
        items: List[CompletionItem]

    class CompletionItemKind:  # type: ignore[override]
        Text = 1
        Method = 2
        Function = 3
        Keyword = 14
        Reference = 18

    @dataclass
    class MarkupContent:  # type: ignore[override]
        kind: str
        value: str

    @dataclass
    class Hover:  # type: ignore[override]
        contents: Any


_COMPILER = AICodeCompiler(strict_mode=True)


def _strip_json_line_comments(raw: str) -> str:
    # Keep this conservative: remove // only outside quoted strings.
    out: List[str] = []
    i = 0
    in_q = False
    esc = False
    while i < len(raw):
        ch = raw[i]
        if in_q:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_q = False
            i += 1
            continue
        if ch == '"':
            in_q = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(raw) and raw[i + 1] == "/":
            # Skip to line end.
            while i < len(raw) and raw[i] not in "\r\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_adapter_registry() -> Dict[str, Any]:
    candidates = [
        Path(__file__).parent / "ADAPTER_REGISTRY.json",
        Path(__file__).parent / "tooling" / "adapter_manifest.json",
        Path(__file__).parent / "docs" / "ADAPTER_REGISTRY.json",
        Path(__file__).parent / "examples" / "golden" / "ADAPTER_REGISTRY.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            return json.loads(_strip_json_line_comments(raw))
        except Exception:
            continue
    return {
        "adapters": {
            "core": {
                "description": "Core utility adapter",
                "targets": {"add": {"args": ["number", "number"], "returns": "number"}},
            }
        }
    }


REGISTRY = load_adapter_registry()


def _clamp_position(lines: Sequence[str], line: int, character: int) -> Tuple[int, int]:
    if not lines:
        return 0, 0
    ln = max(0, min(line, len(lines) - 1))
    ch = max(0, min(character, len(lines[ln])))
    return ln, ch


def build_prefix(source: str, line: int, character: int) -> str:
    lines = source.split("\n")
    if not lines:
        return ""
    ln, ch = _clamp_position(lines, line, character)
    head = lines[:ln]
    cur = lines[ln][:ch]
    return ("\n".join(head) + ("\n" if ln > 0 else "") + cur) if ln > 0 else cur


def apply_completion_candidate(prefix: str, candidate: str) -> str:
    """
    Apply a completion token using compiler-owned prefix transition logic.
    """
    return grammar_apply_candidate_to_prefix(prefix, candidate, tokenizer=_COMPILER)


def _token_spans_for_line(raw_line: str, lineno: int) -> List[Dict[str, Any]]:
    try:
        toks = _COMPILER.tokenize_line_lossless(raw_line, lineno)
    except Exception:
        return []
    return [t for t in toks if t.get("kind") in ("bare", "string")]


def token_under_cursor(source: str, line: int, character: int) -> Optional[Dict[str, Any]]:
    lines = source.split("\n")
    if not lines:
        return None
    ln, ch = _clamp_position(lines, line, character)
    spans = _token_spans_for_line(lines[ln], ln + 1)
    for tok in spans:
        span = tok.get("span") or {}
        start = int(span.get("col_start", 0))
        end = int(span.get("col_end", 0))
        if start <= ch < end:
            return tok
    # Cursor may be at token end; treat as on token for hover friendliness.
    for tok in spans:
        span = tok.get("span") or {}
        if int(span.get("col_end", -1)) == ch:
            return tok
    return None


def _registry_adapter_ops() -> Set[str]:
    out: Set[str] = set()
    adapters = REGISTRY.get("adapters", {}) if isinstance(REGISTRY, dict) else {}
    for adapter_name, adapter_info in adapters.items():
        if not isinstance(adapter_info, dict):
            continue
        targets = adapter_info.get("targets", {})
        if isinstance(targets, dict):
            for target in targets.keys():
                out.add(f"{adapter_name}.{target}")
        verbs = adapter_info.get("verbs", [])
        if isinstance(verbs, list):
            for verb in verbs:
                out.add(f"{adapter_name}.{verb}")
    return out


def registry_enriched_candidates(prefix: str, formal_candidates: Set[str]) -> Set[str]:
    state = parse_prefix_state(prefix)
    if (state.current_op or "") != "R":
        return set()
    if len(state.slots) > 1:
        return set()
    enriched = _registry_adapter_ops()
    # Grammar remains authoritative. Registry candidates must be admissible.
    return set(next_token_mask(prefix, enriched | formal_candidates))


def _candidate_sort_key(cand: str) -> Tuple[int, str]:
    # Keep canonical label refs and ops near top.
    if cand.startswith("->L"):
        return (0, cand)
    if cand in OP_REGISTRY:
        return (1, cand)
    if "." in cand:
        return (2, cand)
    return (3, cand)


def completion_candidates_from_prefix(prefix: str) -> List[str]:
    formal_classes = formal_next_token_classes(prefix)
    formal_priors = set(next_token_priors(prefix))
    sampled = set(sample_tokens_for_classes(set(formal_classes)))
    merged = set(next_token_mask(prefix, formal_priors | sampled))
    merged |= registry_enriched_candidates(prefix, merged)

    # LSP completion list: avoid returning hard newline candidate.
    merged.discard("\n")
    return sorted(merged, key=_candidate_sort_key)


def _completion_items(candidates: Iterable[str]) -> List[CompletionItem]:
    items: List[CompletionItem] = []
    for cand in candidates:
        kind = CompletionItemKind.Text if HAS_PYGLS else 1
        if cand in OP_REGISTRY:
            kind = CompletionItemKind.Keyword if HAS_PYGLS else 14
        elif cand.startswith("->L") or cand.startswith("->"):
            kind = CompletionItemKind.Reference if HAS_PYGLS else 18
        elif "." in cand:
            kind = CompletionItemKind.Function if HAS_PYGLS else 3
        items.append(CompletionItem(label=cand, kind=kind))
    return items


def _op_hover(token_value: str) -> Optional[str]:
    if grammar_is_label_decl(token_value):
        return f"**{token_value}**\n\nLabel declaration (compiler canonical op: `L:`)."
    op = MODULE_ALIASES.get(token_value, token_value)
    spec = OP_REGISTRY.get(op)
    if not spec:
        return None
    scope = spec.get("scope", "top")
    min_slots = int(spec.get("min_slots", 0))
    return f"**{token_value}**\n\nScope: `{scope}`\nMinimum slots: `{min_slots}`"


def _adapter_hover(token_value: str) -> Optional[str]:
    adapters = REGISTRY.get("adapters", {}) if isinstance(REGISTRY, dict) else {}
    if "." in token_value:
        adapter_name, target = token_value.split(".", 1)
        adapter = adapters.get(adapter_name)
        if not isinstance(adapter, dict):
            return None
        targets = adapter.get("targets", {})
        if isinstance(targets, dict) and isinstance(targets.get(target), dict):
            tinfo = targets[target]
            args = tinfo.get("args", [])
            ret = tinfo.get("returns", "?")
            desc = adapter.get("description", "")
            return (
                f"**{adapter_name}.{target}**\n\n"
                f"Args: `{args}`\nReturns: `{ret}`\n\n"
                f"{desc}"
            )
        verbs = adapter.get("verbs", [])
        if isinstance(verbs, list) and target.lower() in {str(v).lower() for v in verbs}:
            notes = adapter.get("notes", adapter.get("description", ""))
            effect = adapter.get("effect_default", "?")
            return f"**{adapter_name}.{target}**\n\nEffect default: `{effect}`\n\n{notes}"
        return None
    adapter = adapters.get(token_value)
    if isinstance(adapter, dict):
        desc = adapter.get("description", "")
        targets = adapter.get("targets", {})
        target_names = sorted(list(targets.keys())) if isinstance(targets, dict) else []
        listed = ", ".join(target_names[:12])
        tail = " ..." if len(target_names) > 12 else ""
        return f"**{token_value}**\n\n{desc}\n\nTargets: {listed}{tail}"
    return None


def _module_op_hover(token_value: str) -> Optional[str]:
    if "." not in token_value:
        return None
    mod, _ = token_value.split(".", 1)
    if mod in KNOWN_MODULES:
        return f"**{token_value}**\n\nModule-prefixed op (`{mod}` namespace)."
    return None


def hover_contents_for_position(source: str, line: int, character: int) -> Optional[str]:
    tok = token_under_cursor(source, line, character)
    if not tok:
        return None
    if tok.get("kind") != "bare":
        return None
    value = str(tok.get("value", "")).strip()
    if not value:
        return None

    for resolver in (_op_hover, _adapter_hover, _module_op_hover):
        out = resolver(value)
        if out:
            return out
    return None


_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def _line_from_message(msg: str) -> Optional[int]:
    # Legacy compatibility only: new compiler diagnostics should carry
    # span/lineno/node metadata instead of relying on text parsing.
    m = _LINE_RE.search(msg or "")
    if not m:
        return None
    try:
        # compiler lines are 1-based
        return max(0, int(m.group(1)) - 1)
    except Exception:
        return None


_OP_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*):")
_LABEL_NODE_RE = re.compile(r"Label\s+'([^']+)':\s+node\s+'([^']+)'", re.IGNORECASE)


def _find_first_line_for_op(op: str, source_lines: Sequence[str]) -> Optional[int]:
    """
    Legacy heuristic fallback only.

    Returns a line only when there is exactly one matching op occurrence.
    If multiple matches exist, returns None to avoid fake precision.
    """
    matches: List[int] = []
    for idx, raw in enumerate(source_lines):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            toks = _COMPILER.tokenize_line_lossless(raw, idx + 1)
            parsed = _COMPILER.parse_line_lossless(toks, raw, idx + 1)
            op_val = str(parsed.get("op_value", "")).strip()
            if not op_val:
                continue
            if MODULE_ALIASES.get(op_val, op_val) == op:
                matches.append(idx)
        except Exception:
            # Keep scanning other lines if one line cannot be tokenized.
            continue
    if len(matches) == 1:
        return matches[0]
    return None


def _line_from_ir_label_node(message: str, ir: Dict[str, Any]) -> Optional[int]:
    m = _LABEL_NODE_RE.search(message or "")
    if not m:
        return None
    lid = str(m.group(1))
    node_id = str(m.group(2))
    labels = ir.get("labels", {})
    if not isinstance(labels, dict):
        return None
    label = labels.get(lid)
    if not isinstance(label, dict):
        return None
    nodes = label.get("nodes", [])
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("id", "")) != node_id:
            continue
        data = node.get("data", {})
        if isinstance(data, dict):
            lineno = data.get("lineno")
            if isinstance(lineno, int):
                return max(0, lineno - 1)
        break
    return None


def resolve_diagnostic_location(item: Any, ir: Dict[str, Any], source_lines: Sequence[str]) -> Tuple[int, str]:
    """
    Resolve line attribution for compiler diagnostics.

    This precedence is contractually ordered for stability/tests.
    Resolution order:
      1) span
      2) lineno
      3) (label_id, node_id) via IR lookup
      4) message regex
      5) op-fallback (heuristic-only)
      6) document fallback
    Returns: (line_idx, provenance)
    """
    if isinstance(item, dict):
        span = item.get("span")
        if isinstance(span, dict):
            line_val = span.get("line")
            if isinstance(line_val, int):
                return max(0, line_val - 1), "span"
        lineno = item.get("lineno")
        if isinstance(lineno, int):
            return max(0, lineno - 1), "lineno"
        label_id = item.get("label_id")
        node_id = item.get("node_id")
        if label_id is not None and node_id is not None:
            ln = _line_from_ir_label_node(
                f"Label '{label_id}': node '{node_id}'",
                ir,
            )
            if ln is not None:
                return ln, "node"

    message = str(item.get("message", "")) if isinstance(item, dict) else str(item)
    ln = _line_from_message(message)
    if ln is not None:
        return ln, "message"

    # Node mapping from plain message text.
    ln = _line_from_ir_label_node(message, ir)
    if ln is not None:
        return ln, "node"

    op_match = _OP_PREFIX_RE.match(message.strip())
    if op_match:
        op = MODULE_ALIASES.get(op_match.group(1), op_match.group(1))
        ln = _find_first_line_for_op(op, source_lines)
        if ln is not None:
            return ln, "op-fallback"

    # Deliberately coarse fallback when no reliable location is available.
    return 0, "document"


def _line_for_diagnostic(message_item: Any, ir: Dict[str, Any], source_lines: Sequence[str]) -> Optional[int]:
    # Backward-compatible helper retained for tests/importers.
    line_idx, prov = resolve_diagnostic_location(message_item, ir, source_lines)
    if prov == "document":
        return None
    return line_idx


def _line_range(source_lines: Sequence[str], line_idx: Optional[int]) -> Range:
    if not source_lines:
        return Range(start=Position(line=0, character=0), end=Position(line=0, character=0))
    if line_idx is None:
        return Range(start=Position(line=0, character=0), end=Position(line=0, character=len(source_lines[0])))
    ln = max(0, min(line_idx, len(source_lines) - 1))
    return Range(start=Position(line=ln, character=0), end=Position(line=ln, character=len(source_lines[ln])))


def _document_anchor_range(source_lines: Sequence[str]) -> Range:
    """
    Non-precise, document-level anchor used when no trustworthy line exists.
    Policy: anchor to first line only (safe single-line anchor).
    """
    return _line_range(source_lines, None)


def _char_offset_to_position(source: str, offset: int) -> Position:
    """Map 0-based character offset in ``source`` to LSP 0-based line/character."""
    offset = max(0, min(offset, len(source)))
    line = 0
    col = 0
    for i, ch in enumerate(source):
        if i == offset:
            return Position(line=line, character=col)
        if ch == "\n":
            line += 1
            col = 0
        else:
            col += 1
    return Position(line=line, character=col)


def _lsp_range_from_structured(d: StructuredDiagnostic, source: str) -> Range:
    if d.span and len(d.span) == 2:
        a, b = int(d.span[0]), int(d.span[1])
        return Range(
            start=_char_offset_to_position(source, a),
            end=_char_offset_to_position(source, max(a, b)),
        )
    lines = source.split("\n")
    # Prefer compiler-style location resolution when lineno is the parser default (1)
    # and the legacy error string omitted "Line N:" (matches heuristic fallbacks).
    loc: Dict[str, Any] = {"message": d.message}
    if d.lineno > 1:
        loc["lineno"] = d.lineno
    line_idx, prov = resolve_diagnostic_location(loc, {"labels": {}}, lines)
    return _diagnostic_range_for_location(lines, line_idx, prov)


def _lsp_diagnostic_from_structured(d: StructuredDiagnostic, source: str) -> Diagnostic:
    rg = _lsp_range_from_structured(d, source)
    msg = f"{d.kind}: {d.message}"
    code = d.contract_violation_reason or d.kind
    try:
        return Diagnostic(
            range=rg,
            message=msg,
            severity=DiagnosticSeverity.Error,
            source="AINL Compiler",
            code=code,
        )
    except TypeError:
        return Diagnostic(
            range=rg,
            message=msg,
            severity=DiagnosticSeverity.Error,
            source="AINL Compiler",
        )


def _diagnostic_range_for_location(
    source_lines: Sequence[str], line_idx: int, provenance: str
) -> Range:
    """
    Convert resolved location to LSP range with explicit provenance policy.
    - Non-document provenance: exact single-line range for resolved line.
    - Document provenance: coarse first-line anchor only.
    """
    if provenance == "document":
        return _document_anchor_range(source_lines)
    return _line_range(source_lines, line_idx)


def compiler_diagnostics(source: str, strict_mode: bool = True) -> List[Diagnostic]:
    comp = AICodeCompiler(strict_mode=strict_mode)
    ctx = CompilerContext()
    try:
        ir = comp.compile(source, emit_graph=True, context=ctx)
    except CompilationDiagnosticError as e:
        return [_lsp_diagnostic_from_structured(d, source) for d in e.diagnostics]
    except Exception as exc:
        lines = source.split("\n")
        msg = {"message": str(exc)}
        line_idx, provenance = resolve_diagnostic_location(msg, {"labels": {}}, lines)
        return [
            Diagnostic(
                range=_diagnostic_range_for_location(lines, line_idx, provenance),
                message=str(exc),
                severity=DiagnosticSeverity.Error,
                source="ainl-compiler",
            )
        ]
    lines = source.split("\n")
    out: List[Diagnostic] = []

    structured = list(ir.get("structured_diagnostics") or [])
    if structured:
        for row in structured:
            if isinstance(row, dict):
                out.append(
                    _lsp_diagnostic_from_structured(
                        StructuredDiagnostic.from_dict(row), source
                    )
                )
        for item in list(ir.get("diagnostics", []) or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("severity", "error")).lower() != "warning":
                continue
            msg = str(item.get("message", ""))
            line_idx, provenance = resolve_diagnostic_location(item, ir, lines)
            out.append(
                Diagnostic(
                    range=_diagnostic_range_for_location(lines, line_idx, provenance),
                    message=msg,
                    severity=DiagnosticSeverity.Warning,
                    source="ainl-compiler",
                )
            )
        return out

    diagnostics = list(ir.get("diagnostics", []) or [])
    if diagnostics:
        for item in diagnostics:
            msg = str(item.get("message", "")) if isinstance(item, dict) else str(item)
            sev = str(item.get("severity", "error")).lower() if isinstance(item, dict) else "error"
            line_idx, provenance = resolve_diagnostic_location(item, ir, lines)
            out.append(
                Diagnostic(
                    range=_diagnostic_range_for_location(lines, line_idx, provenance),
                    message=msg,
                    severity=DiagnosticSeverity.Warning if sev == "warning" else DiagnosticSeverity.Error,
                    source="ainl-compiler",
                )
            )
        return out

    # Compatibility fallback for older compiler outputs without `diagnostics`.
    # TODO(open-core): keep migrating compiler paths toward structured
    # diagnostics (span/lineno/label_id+node_id) so these heuristic/legacy
    # fallbacks can remain backward-compat only and rarely used.
    for err in list(ir.get("errors", []) or []):
        msg = str(err)
        line_idx, provenance = resolve_diagnostic_location(err, ir, lines)
        out.append(
            Diagnostic(
                range=_diagnostic_range_for_location(lines, line_idx, provenance),
                message=msg,
                severity=DiagnosticSeverity.Error,
                source="ainl-compiler",
            )
        )
    for warn in list(ir.get("warnings", []) or []):
        msg = str(warn)
        line_idx, provenance = resolve_diagnostic_location(warn, ir, lines)
        out.append(
            Diagnostic(
                range=_diagnostic_range_for_location(lines, line_idx, provenance),
                message=msg,
                severity=DiagnosticSeverity.Warning,
                source="ainl-compiler",
            )
        )
    return out


def active_label_scope_from_prefix(prefix: str) -> bool:
    return grammar_active_label_scope(prefix, tokenizer=_COMPILER)


def _completions_for_document(source: str, line: int, character: int) -> List[CompletionItem]:
    prefix = build_prefix(source, line, character)
    cands = completion_candidates_from_prefix(prefix)
    return _completion_items(cands)


def _hover_for_document(source: str, line: int, character: int) -> Optional[Hover]:
    contents = hover_contents_for_position(source, line, character)
    if not contents:
        return None
    return Hover(contents=MarkupContent(kind="markdown", value=contents))


if HAS_PYGLS:
    server = LanguageServer("ainl-ls", "v1.0.0")

    @server.feature(TEXT_DOCUMENT_COMPLETION, CompletionParams)
    async def completions(params: CompletionParams) -> CompletionList:
        doc: Document = server.workspace.get_document(params.text_document.uri)
        items = _completions_for_document(doc.source, params.position.line, params.position.character)
        return CompletionList(is_incomplete=False, items=items)

    @server.feature(TEXT_DOCUMENT_HOVER, HoverParams)
    async def hover(params: HoverParams) -> Optional[Hover]:
        doc: Document = server.workspace.get_document(params.text_document.uri)
        return _hover_for_document(doc.source, params.position.line, params.position.character)

    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    @server.feature(TEXT_DOCUMENT_DID_CHANGE)
    async def did_change(params: Any) -> None:
        uri = getattr(params, "text_document", None) and params.text_document.uri
        if not uri:
            return
        doc = server.workspace.get_document(uri)
        diags = compiler_diagnostics(doc.source, strict_mode=True)
        server.publish_diagnostics(uri, diags)

    @server.feature(InitializeParams)
    async def initialize(params: InitializeParams) -> InitializeResult:
        return InitializeResult(
            server_info=InitializeResultServerInfo(name="ainl-ls", version="1.0.0"),
            capabilities={
                "textDocument": {
                    "completion": {"completionItem": {"detailSupport": True, "documentationFormat": ["markdown", "plaintext"]}},
                    "hover": {"dynamicRegistration": True},
                }
            },
        )


if __name__ == "__main__":
    if not HAS_PYGLS:
        print("pygls not available. Install with: pip install pygls", file=sys.stderr)
        raise SystemExit(1)
    logging.basicConfig(level=logging.INFO)
    server.start_io()
