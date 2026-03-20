"""Structured compiler diagnostics for AINL (post-1.0, additive).

``Diagnostic`` + ``CompilationDiagnosticError`` are JSON-friendly.
``CompilerContext`` collects issues during compile when wired from ``compiler_v2``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterator, List, Optional, Sequence, Tuple

# Character span in source text (start inclusive, end exclusive), or None if unknown.
Span = Optional[Tuple[int, int]]


@dataclass(frozen=True)
class Diagnostic:
    """One structured issue found during parse / validate / compile."""

    lineno: int
    col_offset: int
    kind: str
    message: str
    span: Span = None
    label_id: Optional[str] = None
    node_id: Optional[str] = None
    contract_violation_reason: Optional[str] = None
    suggested_fix: Optional[str] = None
    related_span: Span = None

    def __repr__(self) -> str:
        parts = [
            f"lineno={self.lineno}",
            f"col={self.col_offset}",
            f"kind={self.kind!r}",
            f"msg={self.message!r}",
        ]
        if self.span:
            parts.append(f"span={self.span}")
        if self.label_id:
            parts.append(f"label={self.label_id!r}")
        if self.node_id:
            parts.append(f"node={self.node_id!r}")
        return f"Diagnostic({', '.join(parts)})"

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict (tuple spans serialized as two-element lists)."""
        d = asdict(self)
        for key in ("span", "related_span"):
            v = d.get(key)
            if v is not None:
                d[key] = list(v)
        return d

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Diagnostic:
        def _span(x: Any) -> Span:
            if x is None:
                return None
            if isinstance(x, (list, tuple)) and len(x) == 2:
                return (int(x[0]), int(x[1]))
            raise ValueError(f"invalid span: {x!r}")

        return Diagnostic(
            lineno=int(data["lineno"]),
            col_offset=int(data["col_offset"]),
            kind=str(data["kind"]),
            message=str(data["message"]),
            span=_span(data.get("span")),
            label_id=data.get("label_id"),
            node_id=data.get("node_id"),
            contract_violation_reason=data.get("contract_violation_reason"),
            suggested_fix=data.get("suggested_fix"),
            related_span=_span(data.get("related_span")),
        )


class CompilationDiagnosticError(Exception):
    """Raised when compile finished with one or more structured diagnostics (opt-in path)."""

    def __init__(
        self,
        diagnostics: Sequence[Diagnostic],
        source: str,
        *,
        exit_code: int = 1,
    ) -> None:
        self.diagnostics: tuple[Diagnostic, ...] = tuple(diagnostics)
        self.source = source
        self.exit_code = exit_code
        super().__init__(self._format_summary())

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self.diagnostics)

    def _format_summary(self) -> str:
        lines: List[str] = []
        n = len(self.diagnostics)
        lines.append(
            f"CompilationDiagnosticError: {n} diagnostic{'s' if n != 1 else ''}"
        )
        for i, d in enumerate(self.diagnostics, start=1):
            where = f"{d.lineno}:{d.col_offset}"
            if d.label_id:
                where += f" ({d.label_id}"
                if d.node_id:
                    where += f", {d.node_id}"
                where += ")"
            elif d.node_id:
                where += f" (node {d.node_id})"
            lines.append(f"  [{i}] {where} [{d.kind}] {d.message}")
            if d.contract_violation_reason:
                lines.append(f"      reason: {d.contract_violation_reason}")
            if d.suggested_fix:
                lines.append(f"      suggestion: {d.suggested_fix}")
        return "\n".join(lines)

    def to_json_list(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.diagnostics]


class CompilerContext:
    """Mutable collector for :class:`Diagnostic` during a single ``compile()`` run.

    Pass ``context=CompilerContext()`` into :meth:`AICodeCompiler.compile` to opt in
    to structured collection; legacy callers omit ``context`` and behavior is unchanged.
    """

    __slots__ = ("_diagnostics", "_source")

    def __init__(self) -> None:
        self._diagnostics: List[Diagnostic] = []
        self._source: str = ""

    @property
    def diagnostics(self) -> List[Diagnostic]:
        """Collected diagnostics (same list instance for the compile run)."""
        return self._diagnostics

    @property
    def source(self) -> str:
        """Source text last passed to :meth:`reset_for_compile`."""
        return self._source

    def reset_for_compile(self, source_text: str) -> None:
        """Clear diagnostics and bind source for a new compile invocation."""
        self._diagnostics.clear()
        self._source = source_text

    def add(self, diagnostic: Diagnostic) -> None:
        """Append one diagnostic."""
        self._diagnostics.append(diagnostic)

    def extend(self, items: Sequence[Diagnostic]) -> None:
        """Append many diagnostics."""
        self._diagnostics.extend(items)

    def replace_from_error_strings(self, errors: Sequence[str]) -> None:
        """Replace collected diagnostics with structured rows parsed from legacy string errors."""
        self._diagnostics.clear()
        self._diagnostics.extend(error_strings_to_diagnostics(errors))

    def should_raise_after_compile(
        self,
        *,
        strict_mode: bool,
        legacy_errors: Sequence[str],
    ) -> bool:
        """Whether to raise :class:`CompilationDiagnosticError` at end of ``compile``.

        Raises only in **strict** mode when structured diagnostics were collected,
        matching legacy behavior (non-strict returns IR with ``errors`` and does not
        raise). ``legacy_errors`` is kept for API stability / future fatal-only paths.

        Parameters
        ----------
        strict_mode:
            Compiler strict mode flag.
        legacy_errors:
            Typically ``compiler._errors`` (string messages) from the same run.
        """
        del legacy_errors  # reserved; non-strict compile must still return IR with errors
        if not self._diagnostics:
            return False
        return bool(strict_mode)


_SUGGESTION_RE = re.compile(r"\s+Suggestion:\s*(.+)$", re.DOTALL)
_LINE_PREFIX_RE = re.compile(r"^Line\s+(\d+):\s*", re.IGNORECASE)
_LABEL_NODE_RE = re.compile(
    r"Label\s+'([^']+)':\s*node\s+'([^']+)'", re.IGNORECASE
)
_LABEL_HEAD_RE = re.compile(r"Label\s+'([^']+)'")


def infer_diagnostic_kind(message: str) -> str:
    """Coarse classifier for legacy string messages (stable kind strings for tools)."""
    m = message.lower()
    if "unterminated" in m and "string" in m:
        return "syntax_error"
    if "unreachable" in m:
        return "unreachable_node"
    if "does not exist" in m or "undefined" in m or "no legacy.steps" in m:
        return "undeclared_reference"
    if "unknown adapter" in m or "strict adapter" in m:
        return "strict_validation_failure"
    if "requires at least" in m and "slots" in m:
        return "strict_validation_failure"
    if "arity" in m or ("requires" in m and "slot" in m):
        return "strict_validation_failure"
    if "graph node" in m or ("canonical" in m and "n1" in m):
        return "strict_validation_failure"
    return "strict_validation_failure"


def error_strings_to_diagnostics(errors: Sequence[str]) -> List[Diagnostic]:
    """Parse augmented compiler ``_errors`` strings into :class:`Diagnostic` rows.

    Preserves the full human-readable ``message`` (including trailing suggestion text
    for backward compatibility). ``suggested_fix`` is set when ``Suggestion:`` is present.
    """
    out: List[Diagnostic] = []
    for raw in errors:
        if not (raw or "").strip():
            continue
        suggested: Optional[str] = None
        msg = raw
        sm = _SUGGESTION_RE.search(raw)
        if sm:
            suggested = sm.group(1).strip()
            msg = raw[: sm.start()].rstrip()

        lineno = 1
        col_offset = 1
        label_id: Optional[str] = None
        node_id: Optional[str] = None

        lm = _LINE_PREFIX_RE.match(msg)
        if lm:
            lineno = int(lm.group(1))
            msg = msg[lm.end() :].strip()

        nm = _LABEL_NODE_RE.search(msg)
        if nm:
            label_id, node_id = nm.group(1), nm.group(2)
        else:
            lh = _LABEL_HEAD_RE.search(msg)
            if lh:
                label_id = lh.group(1)

        kind = infer_diagnostic_kind(msg)

        out.append(
            Diagnostic(
                lineno=lineno,
                col_offset=col_offset,
                kind=kind,
                message=msg,
                span=None,
                label_id=label_id,
                node_id=node_id,
                contract_violation_reason=None,
                suggested_fix=suggested,
                related_span=None,
            )
        )
    return out


def make_diagnostic(
    *,
    lineno: int,
    col_offset: int,
    kind: str,
    message: str,
    span: Span = None,
    label_id: Optional[str] = None,
    node_id: Optional[str] = None,
    contract_violation_reason: Optional[str] = None,
    suggested_fix: Optional[str] = None,
    related_span: Span = None,
) -> Diagnostic:
    """Convenience factory matching :class:`Diagnostic` fields (keyword-only)."""
    return Diagnostic(
        lineno=lineno,
        col_offset=col_offset,
        kind=kind,
        message=message,
        span=span,
        label_id=label_id,
        node_id=node_id,
        contract_violation_reason=contract_violation_reason,
        suggested_fix=suggested_fix,
        related_span=related_span,
    )


__all__ = [
    "CompilationDiagnosticError",
    "CompilerContext",
    "Diagnostic",
    "Span",
    "error_strings_to_diagnostics",
    "infer_diagnostic_kind",
    "make_diagnostic",
]
