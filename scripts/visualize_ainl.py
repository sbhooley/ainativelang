#!/usr/bin/env python3
"""
Visualize AINL graph IR as Mermaid (and eventually DOT).

Canonical graph data lives in ``ir["labels"]`` (nodes, edges, entry per label);
there is no separate ``ir["graph"]`` key today.
"""
from __future__ import annotations

import argparse
import json
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


def render_mermaid_to_image(
    mermaid_text: str,
    *,
    format: str = "png",
    width: int = 1200,
    height: int = 800,
) -> bytes:
    """
    Render Mermaid text to PNG or SVG bytes via Playwright.

    Raises RuntimeError with actionable install hints when Playwright/browser
    runtime is unavailable.
    """
    if format not in {"png", "svg"}:
        raise ValueError(f"unsupported render format: {format}")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "Playwright is required for --png/--svg export. "
            "Install with: pip install -e '.[dev]' && playwright install chromium"
        ) from e

    # Normalize quoted path-like node IDs (e.g. "main/1/n1") to Mermaid-safe IDs
    # for browser rendering only. CLI text output remains unchanged.
    mermaid_for_render = _normalize_mermaid_ids_for_render(mermaid_text)

    def _run_render(source_text: str) -> bytes:
        mermaid_json = json.dumps(source_text)
        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: white;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
    }}
    #root {{
      width: {width}px;
      min-height: {height}px;
      display: flex;
      align-items: flex-start;
      justify-content: flex-start;
      padding: 16px;
      box-sizing: border-box;
      background: white;
    }}
  </style>
</head>
<body>
  <div id="root"></div>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    (async function () {{
      try {{
        const source = {mermaid_json};
        mermaid.initialize({{ startOnLoad: false, securityLevel: "loose" }});
        const rendered = await mermaid.render("ainl_graph", source);
        const svg = rendered && rendered.svg ? rendered.svg : rendered;
        const root = document.getElementById("root");
        root.innerHTML = svg;
        window.__AINL_RENDER_DONE__ = true;
      }} catch (e) {{
        window.__AINL_RENDER_ERR__ = String(e);
      }}
    }})();
  </script>
</body>
</html>"""

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="load")
            page.wait_for_function(
                "window.__AINL_RENDER_DONE__ === true || window.__AINL_RENDER_ERR__",
                timeout=20000,
            )
            err = page.evaluate("window.__AINL_RENDER_ERR__ || null")
            if err:
                browser.close()
                raise RuntimeError(f"mermaid render failed in browser: {err}")

            if format == "svg":
                svg_html = page.locator("#root svg").first.evaluate("el => el.outerHTML")
                data = svg_html.encode("utf-8")
            else:
                # Screenshot the rendered SVG node only (stable white background).
                data = page.locator("#root svg").first.screenshot(type="png")

            browser.close()
            return data

    try:
        return _run_render(mermaid_for_render)
    except RuntimeError as e:
        if "Parse error" not in str(e):
            raise
        # Fallback for stricter Mermaid parsers: preserve topology/shapes but
        # simplify node labels to parser-safe tokens.
        simplified = _simplify_mermaid_labels_for_render(mermaid_for_render)
        return _run_render(simplified)


def _normalize_mermaid_ids_for_render(mermaid_text: str) -> str:
    """
    Convert quoted path-like IDs to Mermaid-safe alphanumeric IDs for rendering.

    The visualizer intentionally emits quoted IDs (for readability/stability in
    text mode), but Mermaid browser parsing can reject slash-heavy quoted IDs.
    """
    pattern = re.compile(r'"([A-Za-z0-9_./-]+)"')
    id_map: Dict[str, str] = {}
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        raw = m.group(1)
        if "/" not in raw:
            return m.group(0)
        safe = id_map.get(raw)
        if safe is None:
            counter += 1
            safe = f"n{counter}"
            id_map[raw] = safe
        return safe

    return pattern.sub(repl, mermaid_text)


def _simplify_mermaid_labels_for_render(mermaid_text: str) -> str:
    out = mermaid_text
    out = re.sub(r"\[[^\]\n]*\]", "[node]", out)
    out = re.sub(r"\(\([^\)\n]*\)\)", "((jump))", out)
    out = re.sub(r"\{[^\}\n]*\}", "{if}", out)
    return out


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
        "--png",
        metavar="FILE",
        help="Render Mermaid to PNG and write to FILE (or '-' for stdout).",
    )
    p.add_argument(
        "--svg",
        metavar="FILE",
        help="Render Mermaid to SVG and write to FILE (or '-' for stdout).",
    )
    p.add_argument(
        "--width",
        type=int,
        default=1200,
        help="Render width in pixels for --png/--svg (default: 1200).",
    )
    p.add_argument(
        "--height",
        type=int,
        default=800,
        help="Render height in pixels for --png/--svg (default: 800).",
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
    if args.width <= 0 or args.height <= 0:
        print("error: --width and --height must be positive integers", file=sys.stderr)
        return 2

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

    # --- image export mode ---
    export_fmt: Optional[str] = None
    export_out: Optional[str] = None
    if args.png:
        export_fmt = "png"
        export_out = args.png
    elif args.svg:
        export_fmt = "svg"
        export_out = args.svg
    else:
        out_guess = str(args.output or "")
        lower = out_guess.lower()
        if lower.endswith(".png"):
            export_fmt = "png"
            export_out = out_guess
        elif lower.endswith(".svg"):
            export_fmt = "svg"
            export_out = out_guess

    if export_fmt is not None:
        try:
            data = render_mermaid_to_image(
                text,
                format=export_fmt,
                width=args.width,
                height=args.height,
            )
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"error: failed to render Mermaid as {export_fmt}: {e}", file=sys.stderr)
            return 2

        out_bin = export_out if export_out is not None else args.output
        if out_bin in ("-", ""):
            sys.stdout.buffer.write(data)
        else:
            Path(out_bin).write_bytes(data)
        return 0

    # --- existing text output mode ---
    out = args.output
    if out in ("-", ""):
        sys.stdout.write(text)
    else:
        Path(out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
