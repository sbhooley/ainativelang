#!/usr/bin/env python3
"""
Visualize AINL graph IR as Mermaid (and eventually DOT).

Canonical graph data lives in ``ir["labels"]`` (nodes, edges, entry per label);
there is no separate ``ir["graph"]`` key today.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Repo-root execution: ``python scripts/visualize_ainl.py ...``
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from compiler_diagnostics import CompilationDiagnosticError, CompilerContext, Diagnostic  # noqa: E402
from compiler_v2 import AICodeCompiler  # noqa: E402
from scripts.validate_ainl import (  # noqa: E402
    emit_structured_diagnostics_failure,
    resolve_structured_diagnostics_mode,
)
from tooling import graph_api  # noqa: E402


def _cluster_name_for_label(label_id: str) -> str:
    """Subgraph cluster key: first path segment for ``alias/rest``, else ``main``."""
    s = str(label_id)
    if "/" in s:
        return s.split("/", 1)[0]
    return "main"


def _qualified_node_id(label_id: str, node_id: str) -> str:
    """Stable id fragment (before quoting for Mermaid)."""
    lid = str(label_id)
    nid = str(node_id)
    if "/" in lid:
        return f"{lid}/{nid}"
    return f"main/{lid}/{nid}"


def _mermaid_quote_id(q: str) -> str:
    return '"' + q.replace('"', "#quot;") + '"'


def _mermaid_escape_label(text: str) -> str:
    return text.replace('"', "#quot;").replace("\n", " ").replace("]", "#rb;")


def _short_adapter_prefix(adapter: str) -> str:
    if not adapter:
        return ""
    return adapter.split(".", 1)[0]


def _node_display_text(node: Dict[str, Any], *, labels_only: bool) -> str:
    op = str(node.get("op") or "?")
    if labels_only:
        return op
    data = node.get("data") or {}
    if op == "R":
        ap = _short_adapter_prefix(str(data.get("adapter") or ""))
        tgt = data.get("target", "")
        args = data.get("args") or []
        parts: List[str] = [op]
        if ap:
            parts.append(f"({ap})")
        if tgt != "":
            parts.append(str(tgt))
        parts.extend(str(a) for a in args)
        return " ".join(parts) if len(parts) > 1 else op
    if op == "J":
        v = data.get("var")
        if v is not None:
            return f"J {v}"
        return "J"
    if op == "Call":
        return f"Call {data.get('label', '')}".strip()
    if op == "If":
        return "If"
    if op == "Set":
        return f"Set {data.get('var', '')}".strip() or "Set"
    if op in ("Err", "Retry", "Loop", "While"):
        return op
    # Fallback: op + short hash of raw slots if present
    raw = data.get("raw")
    if isinstance(raw, list) and raw:
        return f"{op} " + " ".join(str(x) for x in raw[:4])
    return op


def _label_tail_is_entry_exit(label_id: str) -> bool:
    tail = str(label_id).split("/")[-1]
    return tail == "ENTRY" or tail.startswith("EXIT")


def _mermaid_node_shape_line(qual_quoted: str, display: str, op: str) -> str:
    esc = _mermaid_escape_label(display)
    if op == "If":
        return f"    {qual_quoted}{{{esc}}}"
    if op == "J":
        return f"    {qual_quoted}(({esc}))"
    return f"    {qual_quoted}[{esc}]"


def _resolve_edge_endpoints(
    ir: Dict[str, Any],
    label_id: str,
    edge: Dict[str, Any],
) -> Optional[Tuple[str, str, str, str]]:
    """
    Return (from_label, from_node, to_label, to_node) for an IR edge, or None if skip.
    ``from_label`` / ``to_label`` are IR label ids; node ids are canonical n*.
    """
    from_n = edge.get("from")
    if not from_n:
        return None
    to_kind = edge.get("to_kind") or "node"
    to_val = edge.get("to")
    if to_kind == "label":
        tgt_lid = str(to_val)
        entry = graph_api.label_entry(ir, tgt_lid)
        if not entry:
            return None
        return str(label_id), str(from_n), tgt_lid, str(entry)
    if not to_val:
        return None
    return str(label_id), str(from_n), str(label_id), str(to_val)


def _iter_visual_edges(ir: Dict[str, Any]) -> List[Tuple[str, str, str, str, str, bool]]:
    """
    List of (from_label, from_node, to_label, to_node, port, synthetic_call) from IR
    edges plus synthetic Call → callee entry edges (not always present as explicit IR edges).
    """
    labels = ir.get("labels") or {}
    seen: Set[Tuple[str, str, str, str, str]] = set()
    out: List[Tuple[str, str, str, str, str, bool]] = []

    def add(
        fl: str,
        fn: str,
        tl: str,
        tn: str,
        port: str,
        *,
        synthetic_call: bool = False,
    ) -> None:
        key = (fl, fn, tl, tn, port)
        if key in seen:
            return
        seen.add(key)
        out.append((fl, fn, tl, tn, port, synthetic_call))

    for lid, body in labels.items():
        if not isinstance(body, dict):
            continue
        lid_s = str(lid)
        for e in body.get("edges") or []:
            if not isinstance(e, dict):
                continue
            res = _resolve_edge_endpoints(ir, lid_s, e)
            if res is None:
                continue
            fl, fn, tl, tn = res
            port = str(e.get("port") or "")
            add(fl, fn, tl, tn, port, synthetic_call=False)

        for n in body.get("nodes") or []:
            if not isinstance(n, dict):
                continue
            if n.get("op") != "Call":
                continue
            data = n.get("data") or {}
            callee = data.get("label")
            nid = n.get("id")
            if not callee or not nid:
                continue
            callee_lid = str(callee)
            entry = graph_api.label_entry(ir, callee_lid)
            if entry:
                add(lid_s, str(nid), callee_lid, str(entry), "call", synthetic_call=True)

    return out


def _count_graph_nodes(labels: Dict[str, Any]) -> int:
    """Count IR nodes that would be drawn (excludes empty ``_anon``)."""
    n = 0
    for lid, body in labels.items():
        if not isinstance(body, dict):
            continue
        lid_s = str(lid)
        if lid_s == "_anon" and not body.get("nodes"):
            continue
        for node in body.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                n += 1
    return n


def generate_mermaid(
    ir: Dict[str, Any],
    *,
    with_clusters: bool = True,
    labels_only: bool = False,
) -> str:
    """
    Render ``ir["labels"]`` as a Mermaid ``graph TD`` diagram.

    Subgraphs group labels by include alias (path segment before the first ``/``);
    top-level numeric labels use cluster ``main``.
    """
    labels = ir.get("labels") or {}
    if not labels or _count_graph_nodes(labels) == 0:
        return (
            'graph TD\n'
            '    direction TB\n'
            '    _empty["Empty workflow - no labels found"]\n'
        )

    lines: List[str] = ["graph TD", "    direction TB"]

    # --- collect node statements by cluster ---
    cluster_nodes: Dict[str, List[str]] = {}
    cluster_edges_internal: Dict[str, List[str]] = {}
    flat_internal_edges: List[str] = []
    cross_edges: List[str] = []
    synthetic_cross_edges: List[str] = []
    styled_ids: List[str] = []

    def cluster_for(lid: str) -> str:
        return _cluster_name_for_label(lid)

    for lid, body in sorted(labels.items(), key=lambda x: str(x[0])):
        if not isinstance(body, dict):
            continue
        lid_s = str(lid)
        if lid_s == "_anon" and not body.get("nodes"):
            continue

        cname = cluster_for(lid_s)
        nodes = body.get("nodes") or []
        for n in nodes:
            if not isinstance(n, dict):
                continue
            nid = n.get("id")
            if not nid:
                continue
            q = _qualified_node_id(lid_s, str(nid))
            qq = _mermaid_quote_id(q)
            disp = _node_display_text(n, labels_only=labels_only)
            op = str(n.get("op") or "?")
            stmt = _mermaid_node_shape_line(qq, disp, op)
            if with_clusters:
                cluster_nodes.setdefault(cname, []).append(stmt)
            else:
                lines.append(stmt)
            if _label_tail_is_entry_exit(lid_s):
                styled_ids.append(qq)

    # --- edges ---
    for fl, fn, tl, tn, port, synthetic_call in _iter_visual_edges(ir):
        fq = _mermaid_quote_id(_qualified_node_id(fl, fn))
        tq = _mermaid_quote_id(_qualified_node_id(tl, tn))
        if port and port != "next":
            edge_line = f"    {fq} -->|{_mermaid_escape_label(port)}| {tq}"
        else:
            edge_line = f"    {fq} --> {tq}"

        same_cluster = cluster_for(fl) == cluster_for(tl)
        if with_clusters and same_cluster:
            c = cluster_for(fl)
            cluster_edges_internal.setdefault(c, []).append(edge_line)
        elif not with_clusters and same_cluster:
            flat_internal_edges.append(edge_line)
        elif synthetic_call:
            synthetic_cross_edges.append(edge_line)
        else:
            cross_edges.append(edge_line)

    if with_clusters:
        for cname in sorted(cluster_nodes.keys()):
            lines.append(f'    subgraph c_{_sanitize_subgraph_id(cname)} ["{cname}"]')
            lines.extend(cluster_nodes.get(cname, []))
            lines.extend(cluster_edges_internal.get(cname, []))
            lines.append("    end")
        if synthetic_cross_edges:
            lines.append(
                "    %% Synthetic edges: Call → included label entry (not explicit in IR)"
            )
            lines.extend(synthetic_cross_edges)
        lines.extend(cross_edges)
    else:
        lines.extend(flat_internal_edges)
        if synthetic_cross_edges:
            lines.append(
                "    %% Synthetic edges: Call → included label entry (not explicit in IR)"
            )
            lines.extend(synthetic_cross_edges)
        lines.extend(cross_edges)

    if styled_ids:
        lines.append("    classDef labelstyle fill:#f9f,stroke:#333")
        uniq = sorted(set(styled_ids))
        lines.append("    class " + ",".join(uniq) + " labelstyle")

    return "\n".join(lines) + "\n"


def _sanitize_subgraph_id(name: str) -> str:
    """Mermaid subgraph IDs must not contain ``/`` or spaces; strip other unsafe chars."""
    s = str(name).replace("/", "_").replace(" ", "_")
    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    return s.strip("_") or "g"


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Visualize an AINL file as a Mermaid or DOT control-flow diagram.",
    )
    p.add_argument("path", type=Path, help="Path to a .ainl / .lang source file")
    p.add_argument(
        "--format",
        choices=("mermaid", "dot"),
        default="mermaid",
        help="Output format (default: mermaid)",
    )
    p.add_argument(
        "--output",
        "-o",
        default="-",
        metavar="FILE",
        help='Write diagram here, or "-" for stdout (default: -)',
    )
    p.add_argument(
        "--no-clusters",
        action="store_true",
        help="Do not emit subgraphs (flat qualified node ids).",
    )
    p.add_argument(
        "--labels-only",
        action="store_true",
        help="Minimal node text (op name only for most nodes).",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in diagnostic output on compile failure.",
    )
    p.add_argument(
        "--diagnostics-format",
        choices=("auto", "plain", "json", "rich"),
        default="auto",
        help="Structured diagnostic style when strict compile fails (default: auto).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    path: Path = args.path
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1

    code = path.read_text(encoding="utf-8")
    ctx = CompilerContext()
    try:
        ir = AICodeCompiler(strict_mode=True).compile(
            code,
            emit_graph=True,
            context=ctx,
            source_path=str(path.resolve()),
        )
    except CompilationDiagnosticError as e:
        mode = resolve_structured_diagnostics_mode(
            json_diagnostics_flag=False,
            diagnostics_format=args.diagnostics_format,
            no_color=bool(args.no_color),
            stderr_isatty=sys.stderr.isatty(),
        )
        emit_structured_diagnostics_failure(
            list(e.diagnostics),
            e.source,
            mode=mode,
        )
        return 1

    if ir.get("errors"):
        mode = resolve_structured_diagnostics_mode(
            json_diagnostics_flag=False,
            diagnostics_format=args.diagnostics_format,
            no_color=bool(args.no_color),
            stderr_isatty=sys.stderr.isatty(),
        )
        raw_sd = ir.get("structured_diagnostics") or []
        if raw_sd:
            diags = [Diagnostic.from_dict(d) for d in raw_sd]
            emit_structured_diagnostics_failure(diags, code, mode=mode)
        else:
            print("\n".join(str(x) for x in ir["errors"]), file=sys.stderr)
        return 1

    fmt = args.format
    if fmt == "dot":
        print("error: DOT output is not implemented yet (use --format mermaid).", file=sys.stderr)
        return 2

    text = generate_mermaid(
        ir,
        with_clusters=not args.no_clusters,
        labels_only=bool(args.labels_only),
    )
    out = args.output
    if out in ("-", ""):
        sys.stdout.write(text)
    else:
        Path(out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
