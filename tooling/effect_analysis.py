"""
Effect analysis: per-node effect_tier, per-label effect_summary, and capability/effect sets.
Provides a stable contract for agents (io-read vs io-write, control, meta) and enables
strict checks (defined-before-use, call effect inclusion, adapter contracts).
"""
from typing import Any, Dict, List, Optional, Set, Tuple

# Effect tiers: finer than effect (io|pure|meta) for planning and safety.
EFFECT_TIER_PURE = "pure"
EFFECT_TIER_IO_READ = "io-read"
EFFECT_TIER_IO_WRITE = "io-write"
EFFECT_TIER_CONTROL = "control"
EFFECT_TIER_META = "meta"

# Capability/effect kinds used in effect_summary.effects set.
EFFECT_KIND_DB_READ = "db_read"
EFFECT_KIND_DB_WRITE = "db_write"
EFFECT_KIND_HTTP = "http"
EFFECT_KIND_CACHE_READ = "cache_read"
EFFECT_KIND_CACHE_WRITE = "cache_write"
EFFECT_KIND_QUEUE = "queue"
EFFECT_KIND_TXN = "txn"
EFFECT_KIND_SQLITE = "sqlite"
EFFECT_KIND_FS = "fs"
EFFECT_KIND_MEMORY_READ = "memory_read"
EFFECT_KIND_MEMORY_WRITE = "memory_write"
EFFECT_KIND_TOOL = "tool"
EFFECT_KIND_CALL = "call"
EFFECT_KIND_CONTROL = "control"
EFFECT_KIND_META = "meta"
EFFECT_KIND_COMPUTE = "compute"

# Canonical strict-mode adapter contract:
# adapter.verb -> (effect_tier, effect_kind)
#
# This map is the compiler-owned allowlist for strict adapter validation.
# Unknown adapter.verb remains strict-fail by design.
ADAPTER_EFFECT: Dict[str, Tuple[str, str]] = {
    "core.ADD": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SUB": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MUL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.DIV": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MIN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MAX": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CLAMP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CONCAT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SPLIT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.JOIN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.LOWER": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.UPPER": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.REPLACE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CONTAINS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.PARSE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.STRINGIFY": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.NOW": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ISO": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ISO_TS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ENV": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "core.SUBSTR": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.IDIV": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SLEEP": (EFFECT_TIER_CONTROL, EFFECT_KIND_CONTROL),
    "core.ECHO": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "db.F": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "db.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "db.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.C": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.U": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.D": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "api.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "api.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "api.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "email.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "calendar.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "social.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # apollo-x-bot / bridge-friendly placeholders (strict allowlist; wire in runtime or bridge).
    "x.SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "x.POST_REPLY": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "state.GET_SEEN_IDS": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "state.MARK_SEEN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "classify.SCORE_RELEVANCE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "core.FILTER_HIGH_SCORE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "cache.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "cache.SET": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "queue.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "txn.BEGIN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "txn.COMMIT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "txn.ROLLBACK": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "auth.VALIDATE": (EFFECT_TIER_IO_READ, EFFECT_KIND_CONTROL),
    "ext.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "ext.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.OP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.NEXT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.ECHO": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "http.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "http.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.PATCH": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.HEAD": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "http.OPTIONS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # Config-mapped POST to external executor URLs (optional adapter; same network tier as http.Post).
    "bridge.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "sqlite.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_SQLITE),
    "sqlite.EXECUTE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_SQLITE),
    "fs.READ": (EFFECT_TIER_IO_READ, EFFECT_KIND_FS),
    "fs.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_FS),
    "fs.WRITE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_FS),
    "fs.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_FS),
    "memory.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "memory.APPEND": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "memory.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.PRUNE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "tools.CALL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TOOL),
    # wasm compute calls are treated as pure compute effects.
    "wasm.CALL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
}


def strict_adapter_key(adapter: Any, req_op: Any = "") -> str:
    """Canonical strict contract key for adapter fields (namespace.VERB)."""
    ad = str(adapter or "")
    if "." in ad:
        namespace, ad_verb = ad.split(".", 1)
        return f"{namespace}.{ad_verb.upper()}"
    verb = str(req_op or "").upper() or "F"
    if ad:
        return f"{ad}.{verb}"
    return ""


def strict_adapter_key_for_step(step: Dict[str, Any]) -> str:
    """Canonical strict contract key for compiler/runtime step data."""
    adapter = step.get("adapter") or step.get("src") or ""
    req_op = step.get("req_op")
    # R memory <verb> ... parses as adapter=memory, entity=<verb>, req_op="" → would
    # otherwise become memory.F; fold entity into the verb for strict allowlist checks.
    if (
        isinstance(adapter, str)
        and "." not in adapter
        and adapter.lower() == "memory"
        and not str(req_op or "").strip()
    ):
        ent = (step.get("entity") or step.get("target") or "").strip()
        if ent:
            return strict_adapter_key(adapter, ent)
    return strict_adapter_key(adapter, req_op)


def strict_adapter_is_allowed(key: str) -> bool:
    return bool(key) and key in ADAPTER_EFFECT


def strict_adapter_effect(key: str) -> Optional[Tuple[str, str]]:
    return ADAPTER_EFFECT.get(key)


def _adapter_key(step: Dict[str, Any]) -> str:
    return strict_adapter_key_for_step(step)


def effect_tier_for_node(node: Dict[str, Any]) -> str:
    """Return effect_tier for a single node: pure | io-read | io-write | control | meta."""
    op = node.get("op") or (node.get("data") or {}).get("op", "")
    data = node.get("data") or {}

    if op == "Err":
        return EFFECT_TIER_META
    if op == "Retry":
        return EFFECT_TIER_CONTROL
    if op == "R":
        key = _adapter_key(data)
        tier, _ = strict_adapter_effect(key) or (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP)
        return tier
    if op in ("Call", "QueuePut", "CacheSet", "Tx"):
        return EFFECT_TIER_IO_WRITE
    if op == "CacheGet":
        return EFFECT_TIER_IO_READ
    if op in ("If", "Loop", "While"):
        return EFFECT_TIER_CONTROL
    return EFFECT_TIER_PURE


def effect_kinds_for_node(node: Dict[str, Any]) -> Set[str]:
    """Return set of effect kinds (db_read, http, etc.) for this node."""
    op = node.get("op") or (node.get("data") or {}).get("op", "")
    data = node.get("data") or {}
    out: Set[str] = set()

    if op == "Err":
        out.add(EFFECT_KIND_META)
        return out
    if op == "Retry":
        out.add(EFFECT_KIND_CONTROL)
        return out
    if op == "R":
        key = _adapter_key(data)
        _, kind = strict_adapter_effect(key) or (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP)
        out.add(kind)
        return out
    if op == "Call":
        out.add(EFFECT_KIND_CALL)
        return out
    if op == "CacheGet":
        out.add(EFFECT_KIND_CACHE_READ)
        return out
    if op == "CacheSet":
        out.add(EFFECT_KIND_CACHE_WRITE)
        return out
    if op == "QueuePut":
        out.add(EFFECT_KIND_QUEUE)
        return out
    if op == "Tx":
        out.add(EFFECT_KIND_TXN)
        return out
    if op in ("If", "Loop", "While"):
        out.add(EFFECT_KIND_CONTROL)
    return out


def compute_label_effect_summary(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    entry: Any,
) -> Dict[str, Any]:
    """Compute effect_summary for a label: reads, writes, effects (set of kinds)."""
    all_reads: Set[str] = set()
    all_writes: Set[str] = set()
    all_effects: Set[str] = set()
    for n in nodes:
        for r in n.get("reads") or []:
            all_reads.add(r)
        for w in n.get("writes") or []:
            all_writes.add(w)
        all_effects.update(effect_kinds_for_node(n))
    return {
        "reads": sorted(all_reads),
        "writes": sorted(all_writes),
        "effects": sorted(all_effects),
    }


def annotate_label_with_effect_summary(label: Dict[str, Any]) -> Dict[str, Any]:
    """Add effect_summary and node effect_tier/effect_kinds to a label. Returns new dict."""
    import copy
    out = copy.deepcopy(label)
    nodes = list(out.get("nodes") or [])
    edges = list(out.get("edges") or [])
    entry = out.get("entry")
    new_nodes = []
    for n in nodes:
        nn = dict(n)
        nn["effect_tier"] = effect_tier_for_node(nn)
        nn["effect_kinds"] = sorted(effect_kinds_for_node(nn))
        new_nodes.append(nn)
    out["nodes"] = new_nodes
    if nodes:
        out["effect_summary"] = compute_label_effect_summary(new_nodes, edges, entry)
    else:
        out["effect_summary"] = {"reads": [], "writes": [], "effects": []}
    return out


def annotate_ir_effect_analysis(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Return deep copy of ir with every label annotated with effect_summary and node effect_tier/effect_kinds."""
    import copy
    ir = copy.deepcopy(ir)
    labels = ir.get("labels") or {}
    ir["labels"] = {lid: annotate_label_with_effect_summary(lb) for lid, lb in labels.items()}
    return ir


def annotate_labels_effect_analysis(labels: Dict[str, Any]) -> None:
    """Mutate labels in place: add effect_summary per label and effect_tier/effect_kinds per node."""
    for lid in list(labels.keys()):
        labels[lid] = annotate_label_with_effect_summary(labels.get(lid) or {})


# Vars that are defined by runtime/convention before label runs (no defined-before-use violation).
PREDEFINED_VARS = frozenset({"_auth_present", "_role", "_error", "_call_result", "_loop_last", "_while_last", "_txid"})


def dataflow_defined_before_use(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    entry: Any,
    entry_defined: Optional[Set[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Defined-before-use: forward fixpoint. defined_at[n] = vars defined on at least one path to n.
    Returns (node_id, var) where node reads var and var not in defined_at[node].
    """
    SUCCESS_PORTS = frozenset({"next", "then", "else", "body", "after"})
    node_by_id = {n.get("id"): n for n in nodes if n.get("id")}
    in_edges: Dict[str, List[str]] = {}
    for e in edges:
        if (e.get("port") or "next") not in SUCCESS_PORTS:
            continue
        fr, to = e.get("from"), e.get("to")
        if e.get("to_kind") == "node" and fr and to:
            in_edges.setdefault(to, []).append(fr)
    defined_at: Dict[str, Set[str]] = {}
    if entry:
        defined_at[entry] = set(entry_defined) if entry_defined else set()
    changed = True
    max_iter = 2 * len(nodes) + 10
    while changed and max_iter > 0:
        max_iter -= 1
        changed = False
        for nid, n in node_by_id.items():
            preds = in_edges.get(nid, [])
            if not preds and nid != entry:
                continue
            incoming = set()
            for p in preds:
                if p in defined_at:
                    incoming |= defined_at[p]
            writes = set(n.get("writes") or [])
            new_defs = incoming | writes
            if nid == entry and entry_defined:
                new_defs |= entry_defined
            if nid not in defined_at or defined_at[nid] != new_defs:
                defined_at[nid] = new_defs
                changed = True
    violations: List[Tuple[str, str]] = []
    for nid, n in node_by_id.items():
        reads = set(n.get("reads") or [])
        defs = defined_at.get(nid, set())
        for r in reads:
            if r in PREDEFINED_VARS or r in defs:
                continue
            violations.append((nid, r))
    return violations
