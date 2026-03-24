"""Inter-label defined-before-use propagation (If/else → target label)."""

from __future__ import annotations

from tooling.effect_analysis import dataflow_defined_before_use, propagate_inter_label_entry_defs


def _norm_lid(x):
    if x is None:
        return None
    s = str(x).strip()
    if s.startswith("->L"):
        s = s[3:]
    elif s.startswith("L"):
        s = s[1:]
    if ":" in s:
        s = s.split(":")[-1]
    return s


def test_propagate_inter_label_merges_vars_along_if_else():
    labels = {
        "1": {
            "entry": "n1",
            "nodes": [
                {"id": "n1", "op": "Call", "reads": [], "writes": ["v"]},
                {"id": "n2", "op": "Set", "reads": [], "writes": ["cond"]},
                {"id": "n3", "op": "If", "reads": ["cond"], "writes": []},
            ],
            "edges": [
                {"from": "n1", "to": "n2", "to_kind": "node", "port": "next"},
                {"from": "n2", "to": "n3", "to_kind": "node", "port": "next"},
                {"from": "n3", "to": "2", "to_kind": "label", "port": "then"},
                {"from": "n3", "to": "3", "to_kind": "label", "port": "else"},
            ],
        },
        "2": {"entry": "n1", "nodes": [{"id": "n1", "op": "J", "reads": ["t"], "writes": []}], "edges": []},
        "3": {"entry": "n1", "nodes": [{"id": "n1", "op": "J", "reads": ["v"], "writes": []}], "edges": []},
    }
    entry_map = propagate_inter_label_entry_defs(labels, norm_lid=_norm_lid, endpoint_entry_defs=None)
    assert "v" in entry_map.get("3", set())
    v3 = dataflow_defined_before_use(
        labels["3"]["nodes"],
        labels["3"]["edges"],
        "n1",
        entry_map.get("3"),
    )
    assert v3 == []
