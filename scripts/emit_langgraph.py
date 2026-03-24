#!/usr/bin/env python3
"""
Emit a standalone LangGraph StateGraph wrapper around embedded AINL IR.

Invoked from ``scripts/validate_ainl.py --emit langgraph``. Requires ``langgraph`` at
runtime when executing the generated file.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict


def emit_langgraph_to_path(ir: Dict[str, Any], output_path: Path, *, source_stem: str) -> None:
    """Write a Python module that compiles a single-node LangGraph around ``run_ainl_graph``."""
    text = emit_langgraph_source(ir, source_stem=source_stem)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def emit_langgraph_source(ir: Dict[str, Any], *, source_stem: str) -> str:
    stem = str(source_stem or "ainl_graph").replace("\\", "/").split("/")[-1]
    blob = base64.standard_b64encode(json.dumps(ir, ensure_ascii=False).encode("utf-8")).decode("ascii")

    lines = [
        '"""',
        f"AINL + LangGraph hybrid (emitted from {stem}).",
        "",
        "Run from repo root (or any tree that contains runtime/ and adapters/):",
        f"  python {stem}_langgraph.py",
        "",
        "Optional: pip install langgraph",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import base64",
        "import json",
        "import sys",
        "from pathlib import Path",
        "from typing import Any, Dict, TypedDict",
        "",
        "# Untyped ``dict`` fields: LangGraph introspects TypedDict via get_type_hints; nested",
        "# generics like dict[str, Any] can fail to resolve ``Any`` in that code path on 3.10.",
        "",
        f"_IR_B64 = {blob!r}",
        f"_SOURCE_STEM = {stem!r}",
        "_DEFAULT_LABEL = None  # None → RuntimeEngine.default_entry_label()",
        "",
        "",
        "def _repo_root() -> Path:",
        "    _here = Path(__file__).resolve().parent",
        "    for start in (_here, Path.cwd().resolve()):",
        "        root = start",
        "        for _ in range(14):",
        '            if (root / "runtime" / "engine.py").is_file() and (root / "adapters").is_dir():',
        "                return root",
        "            if root.parent == root:",
        "                break",
        "            root = root.parent",
        "    return _here",
        "",
        "",
        "_ROOT = _repo_root()",
        "if str(_ROOT) not in sys.path:",
        "    sys.path.insert(0, str(_ROOT))",
        "",
        "from runtime.wrappers.langgraph_wrapper import run_ainl_graph  # noqa: E402",
        "",
        "",
        "_IR: Dict[str, Any] | None = None",
        "",
        "",
        "def _ir() -> Dict[str, Any]:",
        "    global _IR",
        "    if _IR is None:",
        "        _IR = json.loads(base64.standard_b64decode(_IR_B64))",
        "    return _IR",
        "",
        "",
        "# Generic state: extend with your own keys (e.g. messages, tenant_id).",
        "# ``ainl_frame`` is copied into the AINL runtime frame for the entry label.",
        "class AinlHybridState(TypedDict, total=False):",
        "    ainl_frame: dict",
        "    ainl_run: dict",
        "",
        "",
        "def ainl_core_node(state: AinlHybridState) -> Dict[str, Any]:",
        '    """Single deterministic node: run the full embedded AINL graph once."""',
        "    frame = dict(state.get(\"ainl_frame\") or {})",
        "    out = run_ainl_graph(_ir(), state=frame, label=_DEFAULT_LABEL)",
        "    return {\"ainl_run\": out, \"ainl_frame\": frame}",
        "",
        "",
        "def build_graph():",
        '    """',
        "    Build and compile a minimal StateGraph: START → ainl_core → END.",
        "",
        "    Extensions:",
        "      - graph.add_conditional_edges(\"ainl_core\", router_fn, {\"a\": \"node_a\", \"b\": \"node_b\"})",
        "      - graph.add_node(\"llm\", ...) for LLM steps that *call into* AINL only when needed",
        '    """',
        "    try:",
        "        from langgraph.graph import END, START, StateGraph",
        "    except ImportError as e:",
        '        raise RuntimeError("Install langgraph: pip install langgraph") from e',
        "    g = StateGraph(AinlHybridState)",
        '    g.add_node("ainl_core", ainl_core_node)',
        '    g.add_edge(START, "ainl_core")',
        '    g.add_edge("ainl_core", END)',
        "    return g.compile()",
        "",
        "",
        'if __name__ == "__main__":',
        "    app = build_graph()",
        '    final = app.invoke({"ainl_frame": {}})',
        "    print(json.dumps(final, default=str, indent=2))",
        "",
    ]
    return "\n".join(lines)
