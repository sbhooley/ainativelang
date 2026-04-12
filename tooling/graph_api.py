"""
Graph query API for agents and tooling. Pure functions over IR; no side effects.
Use these instead of crawling raw JSON so contract and semantics stay in one place.
"""
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

# Dotted graph-memory R verbs → memory_type tier (mirrors compiler_v2._MEMORY_TYPE_MAP).
_MEMORY_TYPE_MAP = {
    "memory.execute": "procedural",
}

# Ports that represent "success" flow (not error/retry).
SUCCESS_PORTS = frozenset({"next", "then", "else", "body", "after"})
ERROR_PORTS = frozenset({"err", "retry", "handler"})

# Max paths and depth to avoid runaway DFS.
MAX_PATHS = 200
MAX_DEPTH = 50


def _iter_eps(eps: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for path, methods in (eps or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, ep in methods.items():
            if isinstance(ep, dict):
                out.append((path, method, ep))
    return out


def endpoint_entry_label(ir: Dict[str, Any], path: str, method: str) -> Optional[str]:
    """Return label_id for the given endpoint (path + method), or None."""
    core = ir.get("services") or {}
    core = core.get("core") or {}
    eps = core.get("eps") or {}
    method = (method or "G").upper()
    for p, m, ep in _iter_eps(eps):
        if p == path and (m == method or ep.get("method", "").upper() == method):
            lid = ep.get("label_id")
            if lid is not None:
                return str(lid).lstrip("L").split(":")[-1]
    return None


def label_nodes(ir: Dict[str, Any], label_id: Union[str, int, Sequence[Any]]) -> Dict[str, Dict[str, Any]]:
    """Return {node_id: node} for the label. Empty dict if label or nodes missing.

    ``label_id`` may be a single label id or a sequence of ids (merged map; later labels win on id collision).
    """
    labels = ir.get("labels") or {}
    if label_id is not None and not isinstance(label_id, (str, int)) and hasattr(label_id, "__iter__"):
        merged: Dict[str, Dict[str, Any]] = {}
        for lid in label_id:
            merged.update(label_nodes(ir, lid))
        return merged
    body = labels.get(str(label_id)) or {}
    nodes = body.get("nodes") or []
    return {n.get("id"): n for n in nodes if n.get("id")}


def label_edges(ir: Dict[str, Any], label_id: Union[str, int, Sequence[Any]]) -> List[Dict[str, Any]]:
    """Return list of edges for the label (concatenated when ``label_id`` is a sequence)."""
    labels = ir.get("labels") or {}
    if label_id is not None and not isinstance(label_id, (str, int)) and hasattr(label_id, "__iter__"):
        out: List[Dict[str, Any]] = []
        for lid in label_id:
            out.extend(label_edges(ir, lid))
        return out
    body = labels.get(str(label_id)) or {}
    return list(body.get("edges") or [])


def emit_edges(ir: Dict[str, Any], label_id: Union[str, int, Sequence[Any]]) -> List[Dict[str, Any]]:
    """Return all emit/data-flow edges for a label (or merged list for a sequence of labels)."""
    labels = ir.get("labels") or {}
    if label_id is not None and not isinstance(label_id, (str, int)) and hasattr(label_id, "__iter__"):
        acc: List[Dict[str, Any]] = []
        for lid in label_id:
            acc.extend(emit_edges(ir, lid))
        return acc
    body = labels.get(str(label_id)) or {}
    return list(body.get("emit_edges") or [])


def data_flow_edges(ir: Dict[str, Any], label_id: Union[str, int, Sequence[Any]]) -> List[Dict[str, Any]]:
    """Return only data-flow edges (port='data') — variable bindings between nodes."""
    return [e for e in emit_edges(ir, label_id) if e.get("port") == "data"]


def memory_nodes(
    ir: Dict[str, Any],
    label_id: Union[str, int, Sequence[Any]],
    memory_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return all nodes with a memory_type field, optionally filtered by type."""
    nodes = label_nodes(ir, label_id)
    mem = [n for n in nodes.values() if "memory_type" in n]
    if memory_type:
        mem = [n for n in mem if n.get("memory_type") == memory_type]
    return mem


def label_entry(ir: Dict[str, Any], label_id: str) -> Optional[str]:
    """Return entry node id for the label, or None."""
    labels = ir.get("labels") or {}
    body = labels.get(str(label_id)) or {}
    return body.get("entry")


def label_exits(ir: Dict[str, Any], label_id: str) -> List[Dict[str, Any]]:
    """Return exits list for the label (each has node, var)."""
    labels = ir.get("labels") or {}
    body = labels.get(str(label_id)) or {}
    return list(body.get("exits") or [])


def _outgoing(
    edges: List[Dict[str, Any]], from_id: str, port_filter: Optional[Set[str]] = None
) -> List[Tuple[str, str, str]]:
    """(to_id, to_kind, port) for edges from from_id. If port_filter set, only those ports."""
    out: List[Tuple[str, str, str]] = []
    for e in edges:
        if e.get("from") != from_id:
            continue
        port = e.get("port") or "next"
        if port_filter is not None and port not in port_filter:
            continue
        out.append((e.get("to"), e.get("to_kind", "node"), port))
    return out


def _incoming(
    edges: List[Dict[str, Any]], to_id: str, port_filter: Optional[Set[str]] = None
) -> List[Tuple[str, str, str]]:
    """(from_id, to_kind, port) for edges into to_id. If port_filter set, only those ports."""
    out: List[Tuple[str, str, str]] = []
    for e in edges:
        if e.get("to") != to_id:
            continue
        port = e.get("port") or "next"
        if port_filter is not None and port not in port_filter:
            continue
        out.append((e.get("from"), e.get("to_kind", "node"), port))
    return out


def successors(
    ir: Dict[str, Any],
    label_id: str,
    node_id: str,
    port: Optional[str] = None,
    kind: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Return [(to_id, port)] for edges from node_id. Filter by port and/or to_kind if given."""
    edges = label_edges(ir, label_id)
    port_set: Optional[Set[str]] = {port} if port else None
    out: List[Tuple[str, str]] = []
    for to_id, to_kind, p in _outgoing(edges, node_id, port_set):
        if kind is not None and to_kind != kind:
            continue
        out.append((to_id, p))
    return out


def predecessors(
    ir: Dict[str, Any],
    label_id: str,
    node_id: str,
    port: Optional[str] = None,
    kind: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Return [(from_id, port)] for edges into node_id. Filter by port and/or to_kind if given."""
    edges = label_edges(ir, label_id)
    port_set: Optional[Set[str]] = {port} if port else None
    out: List[Tuple[str, str]] = []
    for from_id, to_kind, p in _incoming(edges, node_id, port_set):
        if kind is not None and to_kind != kind:
            continue
        out.append((from_id, p))
    return out


def io_nodes(ir: Dict[str, Any], label_id: str) -> List[Dict[str, Any]]:
    """Return nodes with effect == 'io' (R, Call, CacheSet, QueuePut, Tx)."""
    nodes = label_nodes(ir, label_id)
    return [n for n in nodes.values() if n.get("effect") == "io"]


def exit_nodes(ir: Dict[str, Any], label_id: str) -> List[Dict[str, Any]]:
    """Return exit (J) nodes for the label. From exits list or nodes with op=='J'."""
    labels = ir.get("labels") or {}
    body = labels.get(str(label_id)) or {}
    exits = body.get("exits") or []
    nodes = label_nodes(ir, label_id)
    exit_node_ids = {ex.get("node") for ex in exits if ex.get("node")}
    if exit_node_ids:
        return [nodes[nid] for nid in exit_node_ids if nid in nodes]
    return [n for n in nodes.values() if n.get("op") == "J"]


def success_paths(
    ir: Dict[str, Any],
    label_id: str,
    max_paths: int = MAX_PATHS,
    max_depth: int = MAX_DEPTH,
) -> List[List[str]]:
    """Paths (list of node_ids) from entry to an exit (J), following success ports only. Bounded DFS."""
    nodes = label_nodes(ir, label_id)
    edges = label_edges(ir, label_id)
    entry = label_entry(ir, label_id)
    exits = {ex.get("node") for ex in label_exits(ir, label_id) if ex.get("node")}
    if not entry or entry not in nodes:
        return []

    paths: List[List[str]] = []
    stack: List[Tuple[List[str], str, int]] = [([], entry, 0)]

    while stack and len(paths) < max_paths:
        path, cur, depth = stack.pop()
        if depth > max_depth:
            continue
        path = path + [cur]
        if cur in exits:
            paths.append(path)
            continue
        for to_id, to_kind, port in _outgoing(edges, cur, SUCCESS_PORTS):
            if to_kind == "node" and to_id in nodes:
                stack.append((path, to_id, depth + 1))
            # to_kind == "label": we don't follow into other labels here; path ends at branch.

    return paths


def error_paths(
    ir: Dict[str, Any],
    label_id: str,
    from_node: Optional[str] = None,
    max_paths: int = MAX_PATHS,
    max_depth: int = MAX_DEPTH,
) -> List[List[str]]:
    """Paths that include at least one err/retry/handler edge. Bounded DFS. from_node=None uses entry."""
    nodes = label_nodes(ir, label_id)
    edges = label_edges(ir, label_id)
    start = from_node if from_node and from_node in nodes else label_entry(ir, label_id)
    if not start or start not in nodes:
        return []

    paths: List[List[str]] = []
    stack: List[Tuple[List[str], str, int]] = [([], start, 0)]

    while stack and len(paths) < max_paths:
        path, cur, depth = stack.pop()
        if depth > max_depth:
            continue
        path = path + [cur]

        for to_id, to_kind, port in _outgoing(edges, cur, ERROR_PORTS):
            if to_kind == "node" and to_id in nodes:
                paths.append(path + [to_id])
            elif to_kind == "label":
                paths.append(path + [f"L{to_id}"])

        for to_id, to_kind, port in _outgoing(edges, cur, SUCCESS_PORTS):
            if to_kind == "node" and to_id in nodes:
                stack.append((path, to_id, depth + 1))

    return paths


def nodes_using_adapter(
    ir: Dict[str, Any],
    adapter_name: Optional[str] = None,
    *,
    label_id: Optional[str] = None,
    adapter_prefix: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """(label_id, node_id) for every R node using the adapter. Pass adapter_name (e.g. 'db') and/or adapter_prefix (e.g. 'api.'); optional label_id to restrict to one label."""
    out: List[Tuple[str, str]] = []
    labels = ir.get("labels") or {}
    for lid, body in labels.items():
        if label_id is not None and str(lid) != str(label_id):
            continue
        for n in body.get("nodes") or []:
            data = n.get("data") or {}
            if data.get("op") != "R":
                continue
            full_ad = (data.get("adapter") or data.get("src") or "")
            ad = full_ad.split(".", 1)[0] if "." in full_ad else full_ad
            if adapter_name is not None and ad != adapter_name:
                continue
            if adapter_prefix is not None and not full_ad.startswith(adapter_prefix.rstrip(".")) and not ad.startswith(adapter_prefix.rstrip(".")):
                continue
            nid = n.get("id")
            if nid:
                out.append((str(lid), nid))
    return out


def frame_reads(ir: Dict[str, Any], label_id: str) -> Set[str]:
    """Union of all node 'reads' in the label."""
    nodes = label_nodes(ir, label_id)
    out: Set[str] = set()
    for n in nodes.values():
        for r in n.get("reads") or []:
            out.add(r)
    return out


def frame_writes(ir: Dict[str, Any], label_id: str) -> Set[str]:
    """Union of all node 'writes' in the label."""
    nodes = label_nodes(ir, label_id)
    out: Set[str] = set()
    for n in nodes.values():
        for w in n.get("writes") or []:
            out.add(w)
    return out


def trace_annotate_graph(ir: Dict[str, Any], trace_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Overlay execution trace onto the graph. Returns an annotation structure:
      labels -> label_id -> nodes -> node_id -> { exec_count, total_duration_ms, last_error }.
    Events with node_id are counted per (label, node_id). Errors are taken from runtime error
    payloads if present on the trace (e.g. last event when run failed).
    """
    ann: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for ev in trace_events or []:
        lid = ev.get("label")
        nid = ev.get("node_id")
        if not lid or not nid:
            continue
        if lid not in ann:
            ann[lid] = {}
        if nid not in ann[lid]:
            ann[lid][nid] = {"exec_count": 0, "total_duration_ms": 0.0, "last_error": None}
        rec = ann[lid][nid]
        rec["exec_count"] = rec.get("exec_count", 0) + 1
        rec["total_duration_ms"] = rec.get("total_duration_ms", 0.0) + float(ev.get("duration_ms") or 0)
        if ev.get("error"):
            rec["last_error"] = ev.get("error")
    return {"labels": ann}
