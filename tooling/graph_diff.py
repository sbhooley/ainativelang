"""
Graph diff: machine-readable and human-summary diffs between two IRs (e.g. before/after patch).
"""
from typing import Any, Dict, List, Optional, Set, Tuple


def _node_key(n: Dict[str, Any]) -> str:
    return (n.get("id") or "")


def _edge_key(e: Dict[str, Any]) -> Tuple[str, str, str]:
    return (e.get("from"), e.get("to"), e.get("port") or "next")


def _node_data_signature(node: Dict[str, Any]) -> Dict[str, Any]:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return {
        "op": data.get("op"),
        "adapter": data.get("adapter"),
        "target": data.get("target"),
        "args": data.get("args"),
        "out": data.get("out"),
        "cond": data.get("cond"),
        "then": data.get("then"),
        "else": data.get("else"),
        "var": data.get("var"),
        "label": data.get("label"),
        "name": data.get("name"),
        "field": data.get("field"),
        "cmp": data.get("cmp"),
        "value": data.get("value"),
        "ref": data.get("ref"),
        "policy": data.get("policy"),
    }


def graph_diff(
    old_ir: Dict[str, Any],
    new_ir: Dict[str, Any],
    label_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare graph shape for one or all labels. Returns:
      added_nodes, removed_nodes, changed_nodes (id -> {field: (old, new)}),
      added_edges, removed_edges, rewired_edges (same from+port, different to),
      per_label_summary (list of human strings),
      human_summary (single string).
    """
    old_labels = old_ir.get("labels") or {}
    new_labels = new_ir.get("labels") or {}
    label_ids = sorted(set(old_labels.keys()) | set(new_labels.keys()))
    if label_id is not None:
        label_ids = [str(label_id)] if str(label_id) in label_ids else []

    added_nodes: List[Dict[str, Any]] = []
    removed_nodes: List[Dict[str, Any]] = []
    changed_nodes: Dict[Tuple[str, str], Dict[str, Tuple[Any, Any]]] = {}
    added_edges: List[Dict[str, Any]] = []
    removed_edges: List[Dict[str, Any]] = []
    rewired_edges: List[Dict[str, Any]] = []
    per_label_summary: List[str] = []

    for lid in label_ids:
        old_body = old_labels.get(lid) or {}
        new_body = new_labels.get(lid) or {}
        old_nodes = {_node_key(n): n for n in (old_body.get("nodes") or []) if n.get("id")}
        new_nodes = {_node_key(n): n for n in (new_body.get("nodes") or []) if n.get("id")}
        old_edges = {(e.get("from"), e.get("port") or "next"): e for e in (old_body.get("edges") or [])}
        new_edges = {(e.get("from"), e.get("port") or "next"): e for e in (new_body.get("edges") or [])}

        for nid, n in new_nodes.items():
            if nid not in old_nodes:
                added_nodes.append({"label_id": lid, "node": n})
            else:
                diff: Dict[str, Tuple[Any, Any]] = {}
                for k in ("op", "effect", "effect_tier", "reads", "writes"):
                    ov, nv = old_nodes[nid].get(k), n.get(k)
                    if ov != nv:
                        diff[k] = (ov, nv)
                old_sig = _node_data_signature(old_nodes[nid])
                new_sig = _node_data_signature(n)
                if old_sig != new_sig:
                    diff["data"] = (old_sig, new_sig)
                if diff:
                    changed_nodes[(lid, nid)] = diff
        for nid in old_nodes:
            if nid not in new_nodes:
                removed_nodes.append({"label_id": lid, "node": old_nodes[nid]})

        for (fr, port), e in new_edges.items():
            key = (fr, port)
            if key not in old_edges:
                added_edges.append({"label_id": lid, "edge": e})
            else:
                old_e = old_edges[key]
                if old_e.get("to") != e.get("to") or old_e.get("to_kind") != e.get("to_kind"):
                    rewired_edges.append({"label_id": lid, "from": fr, "port": port, "old_to": old_e.get("to"), "new_to": e.get("to")})
        for key in old_edges:
            if key not in new_edges:
                removed_edges.append({"label_id": lid, "edge": old_edges[key]})

        parts: List[str] = []
        if added_nodes or removed_nodes or changed_nodes or added_edges or removed_edges or rewired_edges:
            for d in added_nodes:
                if d.get("label_id") == lid:
                    n = d.get("node", {})
                    parts.append(f"added {n.get('op')} node {n.get('id')}")
            for d in rewired_edges:
                if d.get("label_id") == lid:
                    parts.append(f"rewired {d.get('from')} port={d.get('port')} to {d.get('new_to')}")
            for (cl, cn), cdelta in changed_nodes.items():
                if cl == lid:
                    changed_fields = ",".join(sorted(cdelta.keys()))
                    parts.append(f"changed node {cn} fields={changed_fields}")
            if parts:
                per_label_summary.append(f"Label {lid}: " + "; ".join(parts))

    human_summary = " ".join(per_label_summary) if per_label_summary else "No graph changes."
    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "changed_nodes": changed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "rewired_edges": rewired_edges,
        "per_label_summary": per_label_summary,
        "human_summary": human_summary,
    }
