from __future__ import annotations

import argparse
import json
import shlex
import re
from pathlib import Path
from typing import Any, Dict, List


def _extract_from_source(path: str) -> List[Dict[str, Any]]:
    src = Path(path)
    if not src.exists():
        return []
    calls: List[Dict[str, Any]] = []
    for idx, raw in enumerate(src.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or not line.startswith("R "):
            continue
        if "ptc_runner" not in line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        target = parts[2].strip().upper() if parts[1].startswith("ptc_runner") else parts[1].split(".", 1)[-1].upper()
        if target not in {"RUN"}:
            continue
        payload = parts[3]
        quoted = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', payload)
        if quoted:
            lisp = quoted[0]
            signature = quoted[1] if len(quoted) > 1 else ""
        else:
            try:
                tokens = shlex.split(payload)
            except Exception:
                tokens = []
            lisp = tokens[0] if tokens else payload
            signature = tokens[1] if len(tokens) > 1 else ""
        calls.append({"line": idx, "target": "RUN", "lisp": lisp, "signature": signature})
    return calls


def _extract_from_trajectory(path: str) -> List[Dict[str, Any]]:
    src = Path(path)
    if not src.exists():
        return []
    calls: List[Dict[str, Any]] = []
    with src.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("operation") or "") != "R":
                continue
            inputs = row.get("inputs")
            if not isinstance(inputs, dict):
                continue
            step = inputs.get("step")
            if not isinstance(step, dict):
                continue
            adapter = str(step.get("adapter") or step.get("src") or "").lower()
            target = str(step.get("target") or step.get("entity") or "").upper()
            if adapter != "ptc_runner" or target not in {"RUN"}:
                continue
            args = step.get("args")
            if not isinstance(args, list) or not args:
                continue
            lisp = str(args[0])
            signature = str(args[1]) if len(args) > 1 else ""
            calls.append(
                {
                    "step_id": row.get("step_id"),
                    "label": row.get("label"),
                    "target": target,
                    "lisp": lisp,
                    "signature": signature,
                }
            )
    return calls


def _render_langgraph_snippet(calls: List[Dict[str, Any]]) -> str:
    if not calls:
        return "# No ptc_runner RUN steps detected."
    entries = []
    for i, c in enumerate(calls, start=1):
        entries.append(
            {
                "id": f"ptc_node_{i}",
                "lisp": c.get("lisp", ""),
                "signature": c.get("signature", ""),
            }
        )
    payload_json = json.dumps(entries, ensure_ascii=False, indent=2)
    return (
        "from typing import TypedDict, Dict, Any\n"
        "from langgraph.graph import StateGraph, END\n\n"
        "class State(TypedDict, total=False):\n"
        "    ptc_results: Dict[str, Any]\n\n"
        f"PTC_CALLS = {payload_json}\n\n"
        "def create_ptc_tool_node(ptc_client):\n"
        "    def _node(state: State) -> State:\n"
        "        out = dict(state.get('ptc_results') or {})\n"
        "        for call in PTC_CALLS:\n"
        "            out[call['id']] = ptc_client.call('run', [call['lisp'], call.get('signature') or None])\n"
        "        return {'ptc_results': out}\n"
        "    return _node\n\n"
        "def build_graph(ptc_client):\n"
        "    g = StateGraph(State)\n"
        "    g.add_node('ptc_runner_bridge', create_ptc_tool_node(ptc_client))\n"
        "    g.set_entry_point('ptc_runner_bridge')\n"
        "    g.add_edge('ptc_runner_bridge', END)\n"
        "    return g.compile()\n"
    )


def generate_bridge(*, source: str = "", trajectory: str = "") -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    mode = ""
    if trajectory:
        mode = "trajectory"
        calls = _extract_from_trajectory(trajectory)
    elif source:
        mode = "source"
        calls = _extract_from_source(source)
    snippet = _render_langgraph_snippet(calls)
    return {"ok": True, "mode": mode, "count": len(calls), "calls": calls, "snippet": snippet}


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate LangGraph bridge snippet for ptc_runner steps.")
    ap.add_argument("--source", default="", help="Path to .ainl source")
    ap.add_argument("--trajectory", default="", help="Path to trajectory JSONL")
    ap.add_argument("--out", default="", help="Optional output .py file path")
    ap.add_argument("--json", action="store_true", help="Print full JSON payload (including snippet)")
    args = ap.parse_args()
    if not args.source and not args.trajectory:
        print(json.dumps({"ok": False, "error": "provide --source or --trajectory"}, indent=2))
        raise SystemExit(2)
    out = generate_bridge(source=args.source, trajectory=args.trajectory)
    if args.out:
        Path(args.out).expanduser().write_text(out["snippet"], encoding="utf-8")
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print(out["snippet"])


if __name__ == "__main__":
    main()
