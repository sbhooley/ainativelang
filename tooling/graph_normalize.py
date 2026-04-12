"""
Graph normalizer: guarantees canonical node/edge shape so agents and tooling can rely on it.
Run after graph generation (compiler or hand-built). Ensures:
  - every node has: id, op, effect, reads, writes, data, lineno?
  - every edge has: from, to, to_kind, port
  - effect/reads/writes computed from op rules when missing.
"""
from typing import Any, Dict, List, Optional, Tuple

# Effect by op (everything else defaults to "pure").
OP_EFFECT: Dict[str, str] = {
    "Err": "meta",
    "Retry": "meta",
    "R": "io",
    "Call": "io",
    "QueuePut": "io",
    "CacheSet": "io",
    "Tx": "io",
    "memory.merge": "io",
    "MemoryMerge": "io",
    "persona.update": "io",
}

# Valid ports per source op (edges from this op may only use these ports).
VALID_PORTS: Dict[str, frozenset] = {
    # Control nodes can branch and can also be error/retry sources.
    "If": frozenset({"then", "else", "err", "retry"}),
    "R": frozenset({"next", "err", "retry"}),
    "Loop": frozenset({"body", "after", "next", "err", "retry"}),
    "While": frozenset({"body", "after", "next", "err", "retry"}),
    "Err": frozenset({"next", "handler"}),
    "Retry": frozenset({"next"}),
    # Executable ops can be explicit Err/Retry sources in step lowering.
    "Call": frozenset({"next", "err", "retry"}),
    "J": frozenset(),  # terminal
    "Set": frozenset({"next", "err", "retry"}),
    "Filt": frozenset({"next", "err", "retry"}),
    "Sort": frozenset({"next", "err", "retry"}),
    "X": frozenset({"next", "err", "retry"}),
    "CacheGet": frozenset({"next", "err", "retry"}),
    "CacheSet": frozenset({"next", "err", "retry"}),
    "QueuePut": frozenset({"next", "err", "retry"}),
    "Tx": frozenset({"next", "err", "retry"}),
    "Enf": frozenset({"next", "err", "retry"}),
    "memory.merge": frozenset({"next", "err", "retry"}),
    "MemoryMerge": frozenset({"next", "err", "retry"}),
    "persona.update": frozenset({"next", "err", "retry"}),
}
DEFAULT_PORTS = frozenset({"next"})


def _is_identifier_like(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if s.startswith("$"):
        s = s[1:]
    return s.replace("_", "").isalnum() and not s[0].isdigit() if s else False


def rw_for_step(step: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Deterministic reads/writes from a legacy step. Returns (sorted reads, sorted writes)."""
    op = step.get("op")
    r, w = set(), set()

    def add_read(tok: Any) -> None:
        if tok is None:
            return
        if isinstance(tok, str):
            if tok.startswith("$"):
                r.add(tok[1:])
            elif _is_identifier_like(tok):
                r.add(tok)
        elif isinstance(tok, (int, float, bool)):
            pass  # literal
        else:
            r.add(str(tok))

    if op == "R":
        out = step.get("out", "res")
        if out:
            w.add(out)
        for a in step.get("args") or []:
            add_read(a)

    elif op == "J":
        add_read(step.get("var", "data"))

    elif op == "If":
        cond = step.get("cond", "")
        if isinstance(cond, str) and cond:
            base = cond.rstrip("?")
            if "=" in base:
                base = base.split("=", 1)[0]
            if base.strip():
                add_read(base.strip())

    elif op == "Call":
        out = step.get("out") or "_call_result"
        if out:
            w.add(out)

    elif op == "Set":
        add_read(step.get("ref"))
        name = step.get("name")
        if name:
            w.add(name)

    elif op in ("Filt", "Sort"):
        add_read(step.get("ref"))
        name = step.get("name")
        if name:
            w.add(name)

    elif op == "X":
        for a in step.get("args") or []:
            add_read(a)
        dst = step.get("dst")
        if dst:
            w.add(dst)

    elif op == "Loop":
        add_read(step.get("ref"))
        item = step.get("item", "item")
        if item:
            w.add(item)
        w.add("_loop_last")

    elif op == "While":
        add_read(step.get("cond"))
        w.add("_while_last")

    elif op == "CacheGet":
        add_read(step.get("key"))
        add_read(step.get("fallback"))
        out = step.get("out", "data")
        if out:
            w.add(out)  # CacheGet writes to out var

    elif op == "CacheSet":
        add_read(step.get("key"))
        add_read(step.get("value"))

    elif op == "QueuePut":
        add_read(step.get("value"))
        out = step.get("out")
        if out:
            w.add(out)

    elif op == "Tx":
        if (step.get("action") or "begin").lower() == "begin":
            w.add("_txid")

    elif op == "Enf":
        r.update({"_auth_present", "_role"})

    elif op in ("memory.merge", "MemoryMerge"):
        add_read(step.get("pattern"))
        out = step.get("out", "mm_result")
        if out:
            w.add(out)

    elif op == "persona.update":
        add_read(step.get("trait_name"))
        add_read(step.get("strength"))
        add_read(step.get("learned_from"))

    return sorted(r), sorted(w)


def default_port_for_edge(edge: Dict[str, Any], from_node: Optional[Dict[str, Any]]) -> str:
    """Return port for edge; if missing, default by from_node op."""
    if edge.get("port"):
        return edge["port"]
    if not from_node:
        return "next"
    op = from_node.get("op")
    allowed = VALID_PORTS.get(op, DEFAULT_PORTS)
    if "next" in allowed:
        return "next"
    return sorted(allowed)[0] if allowed else "next"


def normalize_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure node has id, op, effect, reads, writes, data, lineno."""
    out = dict(node)
    data = out.get("data") or {}
    op = out.get("op") or data.get("op", "")
    out.setdefault("op", op)

    if "effect" not in out or out["effect"] not in ("io", "pure", "meta"):
        out["effect"] = OP_EFFECT.get(op, "pure")

    if "reads" not in out or "writes" not in out or not isinstance(out.get("reads"), list) or not isinstance(out.get("writes"), list):
        r, w = rw_for_step(data)
        out["reads"] = r
        out["writes"] = w

    if "lineno" not in out:
        out["lineno"] = data.get("lineno")

    out.setdefault("data", data)
    return out


def normalize_edge(edge: Dict[str, Any], from_node: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure edge has from, to, to_kind, port."""
    out = dict(edge)
    out.setdefault("from", edge.get("from"))
    out.setdefault("to", edge.get("to"))
    out.setdefault("to_kind", edge.get("to_kind", "node"))
    if "port" not in out or out["port"] is None:
        out["port"] = default_port_for_edge(edge, from_node)
    return out


def normalize_label(label: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize nodes and edges of a single label. Returns new dict."""
    out = dict(label)
    nodes = list(out.get("nodes") or [])
    edges = list(out.get("edges") or [])
    node_by_id = {n.get("id"): n for n in nodes if n.get("id")}

    normalized_nodes = [normalize_node(n) for n in nodes]
    node_by_id = {n.get("id"): n for n in normalized_nodes if n.get("id")}
    out["nodes"] = normalized_nodes
    out["edges"] = [normalize_edge(e, node_by_id.get(e.get("from"))) for e in edges]

    if normalized_nodes and out.get("entry") not in node_by_id:
        out["entry"] = normalized_nodes[0].get("id")

    exits = []
    for node in normalized_nodes:
        if node.get("op") != "J":
            continue
        nid = node.get("id")
        if not nid:
            continue
        var = (node.get("data") or {}).get("var", "data")
        exits.append({"node": nid, "var": var})
    if exits:
        out["exits"] = exits
    else:
        out.setdefault("exits", [])
    return out


def normalize_graph(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ir with all labels' nodes/edges normalized."""
    import copy
    ir = copy.deepcopy(ir)
    labels = ir.get("labels") or {}
    ir["labels"] = {lid: normalize_label(lb) for lid, lb in labels.items()}
    return ir


def normalize_labels(labels: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize labels dict in place; returns the same dict (mutates)."""
    for lid in list(labels.keys()):
        labels[lid] = normalize_label(labels.get(lid) or {})
    return labels
