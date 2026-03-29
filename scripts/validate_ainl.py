#!/usr/bin/env python3
"""
AINL Validator / REPL: compile .lang from file or stdin, print IR or errors.
Usage:
  python scripts/validate_ainl.py [file.lang]
  python scripts/validate_ainl.py --emit server [file.lang]
  python scripts/validate_ainl.py --strict workflow.ainl --emit langgraph -o workflow_langgraph.py
  python scripts/validate_ainl.py --emit langgraph workflow.ainl -o workflow_langgraph.py
  python scripts/validate_ainl.py --emit temporal workflow.ainl -o ./out/prefix
  echo "S core web /api" | python scripts/validate_ainl.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_diagnostics import CompilationDiagnosticError, CompilerContext, Diagnostic
from compiler_v2 import AICodeCompiler
from intelligence.signature_enforcer import signature_diagnostics


def _line_start_byte_offset(source: str, lineno: int) -> int:
    """0-based byte offset of the start of 1-based line ``lineno``."""
    if lineno <= 1:
        return 0
    pos = 0
    for _ in range(lineno - 1):
        nxt = source.find("\n", pos)
        if nxt < 0:
            return len(source)
        pos = nxt + 1
    return pos


def _abs_offset_to_line_col(source: str, offset: int) -> Tuple[int, int]:
    """1-based line and column from 0-based absolute byte offset."""
    if not source:
        return 1, 1
    offset = max(0, min(offset, len(source)))
    before = source[:offset]
    line = before.count("\n") + 1
    last_nl = before.rfind("\n")
    col = offset - (last_nl + 1) + 1
    return line, col


def _caret_padding_for_gutter() -> int:
    """Columns before source text in snippet lines (matches ``  > nnnn | ``)."""
    return 11

def _caret_line_for_diagnostic(d: Diagnostic, lines: List[str], source: str) -> Optional[str]:
    """Spaces + carets under the primary line for ``d.span`` or ``col_offset``."""
    ln = d.lineno
    if ln < 1 or ln > len(lines):
        return None
    line = lines[ln - 1]
    line_start = _line_start_byte_offset(source, ln)
    pad = _caret_padding_for_gutter()
    if d.span and isinstance(d.span, (tuple, list)) and len(d.span) == 2:
        s, e = int(d.span[0]), int(d.span[1])
        if line_start <= s < line_start + len(line) + 1:
            c0 = max(0, s - line_start)
            c1 = min(e - line_start, len(line))
            width = max(1, c1 - c0)
            return " " * (pad + c0) + "^" * width
    c0 = max(0, d.col_offset - 1)
    if c0 >= len(line):
        return " " * pad + "^"
    width = max(1, min(len(line) - c0, 40))
    return " " * (pad + c0) + "^" * width


def _format_structured_diagnostics_human(
    diagnostics: List[Diagnostic],
    source: str,
    *,
    use_color: bool,
) -> str:
    """Plain multi-line human report with optional ANSI colors (no rich dependency)."""
    lines = source.split("\n")
    R = "\033[31m" if use_color else ""
    B = "\033[1m" if use_color else ""
    C = "\033[36m" if use_color else ""
    I = "\033[3m" if use_color else ""
    D = "\033[2m" if use_color else ""
    Z = "\033[0m" if use_color else ""
    out: List[str] = []
    for i, d in enumerate(diagnostics, start=1):
        out.append(f"{B}{R}{i}. {d.lineno}:{d.col_offset}{Z} [{d.kind}] {B}{d.message}{Z}")
        if d.label_id or d.node_id:
            bits = []
            if d.label_id:
                bits.append(f"label={d.label_id!r}")
            if d.node_id:
                bits.append(f"node={d.node_id!r}")
            out.append(f"  {' '.join(bits)}")
        if d.suggested_fix:
            out.append(f"  {C}{I}suggestion: {d.suggested_fix}{Z}")
        if d.contract_violation_reason:
            out.append(f"  {D}reason: {d.contract_violation_reason}{Z}")
        if d.related_span and isinstance(d.related_span, (tuple, list)) and len(d.related_span) == 2:
            rl, rc = _abs_offset_to_line_col(source, int(d.related_span[0]))
            out.append(f"  {D}related: line {rl}:{rc}{Z}")
        lo = max(1, d.lineno - 1)
        hi = min(len(lines), d.lineno + 1)
        out.append("  ---")
        for ln in range(lo, hi + 1):
            prefix = ">" if ln == d.lineno else " "
            text = lines[ln - 1] if 1 <= ln <= len(lines) else ""
            out.append(f"  {prefix} {ln:4d} | {text}")
        caret = _caret_line_for_diagnostic(d, lines, source)
        if caret:
            out.append(R + caret + Z)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _print_diagnostics_pretty(
    diagnostics: List[Diagnostic],
    source: str,
    *,
    file,
    use_color: bool,
) -> None:
    """Rich console output when ``rich`` is installed; else plain human format."""
    try:
        from rich.console import Console
        from rich.text import Text
    except ImportError:
        print(
            _format_structured_diagnostics_human(diagnostics, source, use_color=use_color),
            file=file,
            end="",
        )
        return

    no_color = (not use_color) or (hasattr(file, "isatty") and not file.isatty())
    console = Console(file=file, no_color=no_color, highlight=False, soft_wrap=True)
    lines = source.split("\n")

    for i, d in enumerate(diagnostics, start=1):
        head = Text()
        head.append(f"{i}. ", style="bold")
        if no_color:
            head.append(f"{d.lineno}:{d.col_offset}")
        else:
            head.append(f"{d.lineno}:{d.col_offset}", style="bold red")
        head.append(f" [{d.kind}] ", style="dim")
        head.append(d.message or "", style="bold")
        console.print(head)
        if d.label_id or d.node_id:
            bits = []
            if d.label_id:
                bits.append(f"label={d.label_id!r}")
            if d.node_id:
                bits.append(f"node={d.node_id!r}")
            console.print(Text("  " + " ".join(bits), style="dim"))
        if d.suggested_fix:
            console.print(Text(f"  suggestion: {d.suggested_fix}", style="italic cyan"))
        if d.contract_violation_reason:
            console.print(Text(f"  reason: {d.contract_violation_reason}", style="dim"))
        if d.related_span and isinstance(d.related_span, (tuple, list)) and len(d.related_span) == 2:
            rl, rc = _abs_offset_to_line_col(source, int(d.related_span[0]))
            console.print(Text(f"  related: line {rl}:{rc}", style="dim"))

        lo = max(1, d.lineno - 1)
        hi = min(len(lines), d.lineno + 1)
        console.print(Text("  ---", style="dim"))
        for ln in range(lo, hi + 1):
            prefix = ">" if ln == d.lineno else " "
            body = lines[ln - 1] if 1 <= ln <= len(lines) else ""
            t = Text()
            t.append(f"  {prefix} {ln:4d} | ", style="dim")
            t.append(body)
            console.print(t)
        caret = _caret_line_for_diagnostic(d, lines, source)
        if caret:
            console.print(Text(caret, style="red") if not no_color else Text(caret))
        console.print()


def _rich_available() -> bool:
    try:
        import rich.console  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_structured_diagnostics_mode(
    *,
    json_diagnostics_flag: bool,
    diagnostics_format: str,
    no_color: bool,
    stderr_isatty: bool,
) -> str:
    """Return ``json``, ``rich``, or ``plain`` for structured compile failure output.

    * ``--json-diagnostics`` forces ``json`` (legacy alias).
    * ``auto`` → ``rich`` if the rich package is installed, stderr is a TTY, and
      ``--no-color`` was not set; otherwise ``plain``.
    * ``rich`` falls back to ``plain`` when rich is missing or ``--no-color`` is set.
    """
    if json_diagnostics_flag:
        return "json"
    fmt = (diagnostics_format or "auto").strip().lower()
    if fmt == "json":
        return "json"
    if fmt == "plain":
        return "plain"
    if fmt == "rich":
        if no_color or not _rich_available():
            return "plain"
        return "rich"
    if fmt == "auto":
        if _rich_available() and stderr_isatty and not no_color:
            return "rich"
        return "plain"
    return "plain"


def emit_structured_diagnostics_failure(
    diags: List[Diagnostic],
    src: str,
    *,
    mode: str,
) -> None:
    """Print structured failure: ``json`` to stdout; ``rich``/``plain`` to stderr."""
    if mode == "json":
        print(json.dumps([d.to_dict() for d in diags], indent=2))
        return
    if mode == "rich":
        _print_diagnostics_pretty(diags, src, file=sys.stderr, use_color=True)
        return
    print(
        _format_structured_diagnostics_human(diags, src, use_color=False),
        file=sys.stderr,
        end="",
    )


def compile_and_validate(
    code: str,
    *,
    strict: bool = False,
    strict_reachability: bool = False,
    use_structured: bool = False,
) -> dict:
    """Compile ``code``. With ``use_structured``, attach :class:`CompilerContext` for native diagnostics.

    When ``strict`` is True and validation fails, structured diagnostics are available if
    ``use_structured`` is True (the CLI enables this for every ``--strict`` run).
    """
    c = AICodeCompiler(strict_mode=strict, strict_reachability=strict_reachability)
    ctx: Optional[CompilerContext] = CompilerContext() if use_structured else None
    try:
        ir = c.compile(code, emit_graph=True, context=ctx)
        # Additive diagnostics: optional R-signature metadata linting via comments.
        extra_diags = signature_diagnostics(code)
        if extra_diags:
            ir.setdefault("diagnostics", [])
            ir["diagnostics"].extend(extra_diags)
        if ir.get("errors"):
            return {"ok": False, "errors": ir.get("errors", []), "ir": ir}
        return {"ok": True, "ir": ir}
    except CompilationDiagnosticError as e:
        return {
            "ok": False,
            "structured": True,
            "diagnostics": list(e.diagnostics),
            "source": e.source,
            "error": str(e),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate AINL and optionally emit artifacts")
    ap.add_argument("file", nargs="?", help="Path to .lang file (default: stdin)")
    ap.add_argument(
        "--emit",
        choices=[
            "ir",
            "server",
            "react",
            "openapi",
            "prisma",
            "sql",
            "hyperspace",
            "solana-client",
            "blockchain-client",
            "langgraph",
            "temporal",
            "hermes-skill",
        ],
        default="ir",
        help=(
            "Emit artifact instead of IR JSON. "
            "Hybrid interop: langgraph (StateGraph wrapper → docs/hybrid_langgraph.md), "
            "temporal (*_activities.py + *_workflow.py → docs/hybrid_temporal.md). "
            "Blockchain: solana-client or blockchain-client → single-file Solana client (see docs/emitters/README.md). "
            "Typical strict path: --strict <file.ainl> --emit langgraph|temporal -o … "
            "Overview: docs/HYBRID_GUIDE.md"
        ),
    )
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output path: hyperspace (default hyperspace_agent.py), solana-client|blockchain-client (default solana_client.py), "
            "langgraph (default <stem>_langgraph.py), "
            "temporal (dir or .py prefix — docs/hybrid_temporal.md). See docs/HYBRID_GUIDE.md"
        ),
    )
    ap.add_argument(
        "--lint-canonical",
        action="store_true",
        help="Print warning-only canonical-lint diagnostics to stderr without failing the compile",
    )
    ap.add_argument("--no-json", action="store_true", help="Print IR as Python repr (for debugging)")
    ap.add_argument("--strict", action="store_true", help="Enable strict compiler validation")
    ap.add_argument(
        "--strict-reachability",
        action="store_true",
        help="Enable strict reachability checks (implies --strict)",
    )
    ap.add_argument(
        "--json-diagnostics",
        action="store_true",
        help="Legacy alias for --diagnostics-format=json (stdout JSON only on failure)",
    )
    ap.add_argument(
        "--diagnostics-format",
        choices=["auto", "plain", "json", "rich"],
        default="auto",
        help=(
            "On structured failure: auto (rich if rich+TTY and not --no-color), plain (text), "
            "json (stdout only), rich (requires rich package; use plain if missing or --no-color)"
        ),
    )
    ap.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colors; forces plain diagnostic output instead of rich styling",
    )
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            code = f.read()
    else:
        code = sys.stdin.read()

    strict = bool(args.strict or args.strict_reachability)
    # Strict CLI runs always collect structured diagnostics so humans get rich/plain reports.
    use_structured = bool(args.json_diagnostics or strict)
    result = compile_and_validate(
        code,
        strict=strict,
        strict_reachability=bool(args.strict_reachability),
        use_structured=use_structured,
    )
    if not result["ok"]:
        if result.get("structured"):
            diags: List[Diagnostic] = result.get("diagnostics") or []
            src = str(result.get("source") or code)
            mode = resolve_structured_diagnostics_mode(
                json_diagnostics_flag=bool(args.json_diagnostics),
                diagnostics_format=str(args.diagnostics_format),
                no_color=bool(args.no_color),
                stderr_isatty=sys.stderr.isatty(),
            )
            emit_structured_diagnostics_failure(diags, src, mode=mode)
        elif "errors" in result:
            for err in result["errors"]:
                print(err, file=sys.stderr)
        else:
            print(result.get("error", ""), file=sys.stderr)
        sys.exit(1)

    ir = result["ir"]

    if args.lint_canonical:
        warning_diags = [
            d
            for d in (ir.get("diagnostics") or [])
            if isinstance(d, dict) and d.get("severity") == "warning"
        ]
        for diag in warning_diags:
            code_d = diag.get("code") or "AINL_COMPILE_WARNING"
            lineno = diag.get("lineno")
            prefix = f"Line {lineno}: " if isinstance(lineno, int) else ""
            print(f"{prefix}{code_d}: {diag.get('message', '')}", file=sys.stderr)

    if args.emit == "ir":
        if args.no_json:
            print(ir)
        else:

            def to_jsonable(obj):
                if isinstance(obj, dict):
                    return {k: to_jsonable(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [to_jsonable(x) for x in obj]
                return obj

            print(json.dumps(to_jsonable(ir), indent=2))
        return

    c = AICodeCompiler()
    if args.emit == "server":
        print(c.emit_server(ir))
    elif args.emit == "react":
        print(c.emit_react(ir))
    elif args.emit == "openapi":
        print(c.emit_openapi(ir))
    elif args.emit == "prisma":
        print(c.emit_prisma_schema(ir))
    elif args.emit == "sql":
        print(c.emit_sql_migrations(ir, dialect="postgres"))
    elif args.emit == "hyperspace":
        stem = Path(args.file).stem if args.file else "ainl_graph"
        content = c.emit_hyperspace_agent(ir, source_stem=stem)
        out = Path(args.output).expanduser() if args.output else Path.cwd() / "hyperspace_agent.py"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(
            json.dumps(
                {"ok": True, "emit": "hyperspace", "path": str(out.resolve()), "source_stem": stem},
                indent=2,
            )
        )
    elif args.emit in ("solana-client", "blockchain-client"):
        stem = Path(args.file).stem if args.file else "ainl_graph"
        content = c.emit_solana_client(ir, source_stem=stem)
        out = Path(args.output).expanduser() if args.output else Path.cwd() / "solana_client.py"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "emit": args.emit,
                    "path": str(out.resolve()),
                    "source_stem": stem,
                },
                indent=2,
            )
        )
    elif args.emit == "langgraph":
        _scripts_dir = Path(__file__).resolve().parent
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))
        import emit_langgraph  # type: ignore

        stem = Path(args.file).stem if args.file else "ainl_graph"
        out = Path(args.output).expanduser() if args.output else Path.cwd() / f"{stem}_langgraph.py"
        emit_langgraph.emit_langgraph_to_path(ir, out, source_stem=stem)
        print(
            json.dumps(
                {"ok": True, "emit": "langgraph", "path": str(out.resolve()), "source_stem": stem},
                indent=2,
            )
        )
    elif args.emit == "temporal":
        _scripts_dir = Path(__file__).resolve().parent
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))
        import emit_temporal  # type: ignore

        stem = Path(args.file).stem if args.file else "ainl_graph"
        out_dir, file_base = emit_temporal.resolve_temporal_output_dir_and_base(args.output, stem)
        out_dir.mkdir(parents=True, exist_ok=True)
        act_p, wf_p = emit_temporal.emit_temporal_pair(ir, output_dir=out_dir, source_stem=file_base)
        print(
            json.dumps(
                {
                    "ok": True,
                    "emit": "temporal",
                    "activities_path": str(act_p.resolve()),
                    "workflow_path": str(wf_p.resolve()),
                    "source_stem": stem,
                    "file_base": file_base,
                },
                indent=2,
            )
        )
    elif args.emit == "hermes-skill":
        stem = Path(args.file).stem if args.file else "ainl_graph"
        out_dir = Path(args.output).expanduser() if args.output else Path.cwd() / f"{stem}_hermes_skill"
        out_dir.mkdir(parents=True, exist_ok=True)

        bundle = c.emit_hermes_skill_bundle(ir, ainl_source=code, skill_name=stem, source_stem=stem)
        written = []
        for rel, content in sorted(bundle.items()):
            p = out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(str(p.resolve()))
        print(json.dumps({"ok": True, "emit": "hermes-skill", "dir": str(out_dir.resolve()), "files": written}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
