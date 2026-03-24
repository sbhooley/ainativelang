"""
Tests for tooling/graph_normalize.py and tooling/graph_api.py.
Run: pytest tests/test_graph_tooling.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.graph_normalize import normalize_graph, normalize_labels, rw_for_step
from tooling.graph_api import (
    endpoint_entry_label,
    label_nodes,
    label_edges,
    success_paths,
    error_paths,
    frame_reads,
    frame_writes,
    nodes_using_adapter,
    trace_annotate_graph,
)
from tooling.graph_rewrite import apply_patch
from tooling.graph_safe_edit import safe_apply_patch
from tooling.graph_diff import graph_diff


def test_compile_produces_normalized_nodes_with_port():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: R db.F User * ->data J data\n")
    assert not ir.get("errors"), ir.get("errors")
    nodes = ir["labels"]["1"]["nodes"]
    assert len(nodes) >= 2
    for n in nodes:
        assert "reads" in n and isinstance(n["reads"], list)
        assert "writes" in n and isinstance(n["writes"], list)
        assert n.get("effect") in ("io", "pure", "meta")
    edges = ir["labels"]["1"]["edges"]
    assert any(e.get("port") == "next" for e in edges)


def test_endpoint_entry_label():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /products G ->L1\nL1: J data\n")
    assert endpoint_entry_label(ir, "/products", "G") == "1"
    assert endpoint_entry_label(ir, "/missing", "G") is None


def test_label_nodes_and_edges():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: R db.F User * ->data J data\n")
    n = label_nodes(ir, "1")
    assert "n1" in n and n["n1"]["op"] == "R"
    assert "n2" in n and n["n2"]["op"] == "J"
    e = label_edges(ir, "1")
    assert len(e) >= 1 and e[0].get("from") == "n1" and e[0].get("to") == "n2"


def test_success_paths():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: R db.F User * ->data J data\n")
    paths = success_paths(ir, "1")
    assert paths and paths[0] == ["n1", "n2"]


def test_frame_reads_writes():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: R db.F User * ->data J data\n")
    r, w = frame_reads(ir, "1"), frame_writes(ir, "1")
    assert "data" in w
    assert "data" in r


def test_nodes_using_adapter():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: R db.F User * ->data J data\n")
    adapter_nodes = nodes_using_adapter(ir, "db")
    assert ("1", "n1") in adapter_nodes


def test_normalize_graph_fills_missing_fields():
    ir = {
        "labels": {
            "1": {
                "nodes": [{"id": "n1", "op": "R", "data": {"op": "R", "out": "res"}}],
                "edges": [{"from": "n1", "to": "n2", "to_kind": "node"}],
                "entry": "n1",
                "exits": [],
            }
        }
    }
    out = normalize_graph(ir)
    n1 = out["labels"]["1"]["nodes"][0]
    assert n1.get("effect") == "io"
    assert "reads" in n1 and "writes" in n1
    assert out["labels"]["1"]["edges"][0].get("port") == "next"


def test_rw_for_step_r():
    r, w = rw_for_step({"op": "R", "out": "x"})
    assert "x" in w
    assert r == [] or "x" not in r


def test_apply_patch_add_node():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: Set x 1 J x\n")
    assert not ir.get("errors"), ir.get("errors")
    new_ir, err = apply_patch(
        ir,
        {
            "op": "add_node",
            "label_id": "1",
            "node": {"id": "n3", "op": "Set", "data": {"dst": "x", "val": 2}},
            "after_node_id": "n1",
            "new_edges": [{"from": "n1", "to": "n3", "to_kind": "node", "port": "next"}],
        },
        strict_validate=True,
    )
    assert err is None, err
    assert new_ir is not None
    nids = [n["id"] for n in new_ir["labels"]["1"]["nodes"]]
    assert "n3" in nids


def test_apply_patch_invalid_label():
    ir = {"labels": {"1": {"nodes": [{"id": "n1"}], "edges": [], "entry": "n1", "exits": []}}}
    new_ir, err = apply_patch(ir, {"op": "add_node", "label_id": "missing", "node": {"id": "n2", "op": "J"}})
    assert new_ir is None and err is not None
    assert err.get("code") == "PATCH_LABEL"


def test_graph_diff():
    old_ir = {
        "labels": {
            "1": {
                "nodes": [{"id": "n1", "op": "R"}, {"id": "n2", "op": "J"}],
                "edges": [{"from": "n1", "to": "n2", "port": "next"}],
                "entry": "n1",
                "exits": [],
            }
        }
    }
    new_ir = {
        "labels": {
            "1": {
                "nodes": [{"id": "n1", "op": "R"}, {"id": "n2", "op": "J"}, {"id": "n3", "op": "Set"}],
                "edges": [{"from": "n1", "to": "n3", "port": "next"}, {"from": "n3", "to": "n2", "port": "next"}],
                "entry": "n1",
                "exits": [],
            }
        }
    }
    d = graph_diff(old_ir, new_ir, label_id="1")
    assert len(d["added_nodes"]) == 1
    assert d["added_nodes"][0]["node"]["id"] == "n3"
    assert len(d["rewired_edges"]) >= 1
    assert "human_summary" in d


def test_graph_diff_detects_payload_changes():
    old_ir = {
        "labels": {
            "1": {
                "nodes": [
                    {"id": "n1", "op": "R", "data": {"op": "R", "adapter": "core.ADD", "target": "2", "args": ["3"], "out": "x"}},
                    {"id": "n2", "op": "J", "data": {"op": "J", "var": "x"}},
                ],
                "edges": [{"from": "n1", "to": "n2", "port": "next"}],
                "entry": "n1",
                "exits": [],
            }
        }
    }
    new_ir = {
        "labels": {
            "1": {
                "nodes": [
                    {"id": "n1", "op": "R", "data": {"op": "R", "adapter": "core.ADD", "target": "2", "args": ["4"], "out": "x"}},
                    {"id": "n2", "op": "J", "data": {"op": "J", "var": "x"}},
                ],
                "edges": [{"from": "n1", "to": "n2", "port": "next"}],
                "entry": "n1",
                "exits": [],
            }
        }
    }
    d = graph_diff(old_ir, new_ir, label_id="1")
    assert ("1", "n1") in d["changed_nodes"]
    assert "data" in d["changed_nodes"][("1", "n1")]


def test_trace_annotate_graph():
    ir = {"labels": {"1": {"nodes": [{"id": "n1"}, {"id": "n2"}], "entry": "n1", "exits": []}}}
    trace = [
        {"label": "1", "node_id": "n1", "duration_ms": 10},
        {"label": "1", "node_id": "n1", "duration_ms": 5},
        {"label": "1", "node_id": "n2", "duration_ms": 2},
    ]
    ann = trace_annotate_graph(ir, trace)
    assert ann["labels"]["1"]["n1"]["exec_count"] == 2
    assert ann["labels"]["1"]["n1"]["total_duration_ms"] == 15.0
    assert ann["labels"]["1"]["n2"]["exec_count"] == 1
    assert ann["labels"]["1"]["n2"]["total_duration_ms"] == 2.0


def test_compiled_ir_has_graph_schema_version():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: J data\n")
    assert not ir.get("errors"), ir.get("errors")
    assert ir.get("graph_schema_version") == "1.0"


def test_graph_normalize_roundtrip():
    """Round-trip: normalize_graph then annotate_ir_effect_analysis leaves graph valid."""
    from tooling.graph_normalize import normalize_graph
    from tooling.effect_analysis import annotate_ir_effect_analysis

    ir = {
        "labels": {
            "1": {
                "nodes": [
                    {"id": "n1", "op": "R", "data": {"op": "R", "adapter": "db.F", "out": "x"}},
                    {"id": "n2", "op": "J", "data": {"op": "J", "var": "x"}},
                ],
                "edges": [{"from": "n1", "to": "n2", "to_kind": "node"}],
                "entry": "n1",
                "exits": [{"node": "n2", "var": "x"}],
            }
        }
    }
    ir = normalize_graph(ir)
    ir = annotate_ir_effect_analysis(ir)
    body = ir["labels"]["1"]
    assert body["nodes"][0].get("effect") == "io"
    assert body["nodes"][0].get("effect_tier") == "io-read"
    assert body.get("effect_summary") and "effects" in body["effect_summary"]


def test_err_at_node_id_emits_err_edge_from_that_node():
    """Err @n1 ->L9 produces an err edge from n1 to the Err node (not just from previous node)."""
    src = """
S core web /api
E /x G ->L1
L1: R api.G /x ->data Err @n1 ->L9 Set data 0 J data
L9: J data
"""
    c = AICodeCompiler()
    ir = c.compile(src)
    assert not ir.get("errors"), ir.get("errors")
    edges = ir["labels"]["1"]["edges"]
    err_edges = [e for e in edges if e.get("port") == "err"]
    assert len(err_edges) == 1, "expect one err edge"
    assert err_edges[0]["from"] == "n1", "err edge must be from n1 (the R node)"
    assert err_edges[0]["to"] == "n2", "err edge must go to the Err node (n2)"
    nodes = ir["labels"]["1"]["nodes"]
    assert nodes[0]["id"] == "n1" and nodes[0]["op"] == "R"
    assert nodes[1]["id"] == "n2" and nodes[1]["op"] == "Err"


def test_retry_at_node_id_emits_retry_edge_from_that_node():
    """Retry @n1 2 100 produces a retry edge from n1 to the Retry node."""
    src = """
S core web /api
E /x G ->L1
L1: R api.G /x ->data Retry @n1 2 100 Set data 0 J data
"""
    c = AICodeCompiler()
    ir = c.compile(src)
    assert not ir.get("errors"), ir.get("errors")
    edges = ir["labels"]["1"]["edges"]
    retry_edges = [e for e in edges if e.get("port") == "retry"]
    assert len(retry_edges) == 1
    assert retry_edges[0]["from"] == "n1"
    assert retry_edges[0]["to"] == "n2"
    nodes = ir["labels"]["1"]["nodes"]
    assert nodes[0]["op"] == "R" and nodes[1]["op"] == "Retry"


def test_safe_apply_patch_returns_diff_and_report():
    c = AICodeCompiler()
    ir = c.compile("S core web /api\nE /x G ->L1\nL1: Set x 1 J x\n")
    assert not ir.get("errors"), ir.get("errors")
    patch = {
        "op": "add_node",
        "label_id": "1",
        "node": {"id": "n3", "op": "Set", "data": {"op": "Set", "dst": "x", "val": 2}},
        "after_node_id": "n1",
        "new_edges": [{"from": "n1", "to": "n3", "to_kind": "node", "port": "next"}],
    }
    res = safe_apply_patch(ir, patch)
    assert res.get("ok") is True, res
    new_ir = res["ir"]
    diff = res["diff"]
    report = res["report"]
    nids = [n["id"] for n in new_ir["labels"]["1"]["nodes"]]
    assert "n3" in nids
    assert any(d["node"]["id"] == "n3" for d in diff["added_nodes"])
    # Oversight report should include label id 1 and endpoint /x G.
    assert "1" in report["label_ids"]
    assert any(ep["path"] == "/x" and ep["method"] == "G" for ep in report["endpoints_affected"])


def test_err_at_node_id_emits_err_edge_from_that_node():
    """Err @n1 ->L9 produces an err edge from n1 to the Err node (not just from previous node)."""
    src = """
S core web /api
E /x G ->L1
L1: R api.G /x ->data Err @n1 ->L9 Set data 0 J data
L9: J data
"""
    c = AICodeCompiler()
    ir = c.compile(src)
    assert not ir.get("errors"), ir.get("errors")
    edges = ir["labels"]["1"]["edges"]
    err_edges = [e for e in edges if e.get("port") == "err"]
    assert len(err_edges) == 1, "expect one err edge"
    assert err_edges[0]["from"] == "n1", "err edge must be from n1 (the R node)"
    assert err_edges[0]["to"] == "n2", "err edge must go to the Err node (n2)"
    nodes = ir["labels"]["1"]["nodes"]
    assert nodes[0]["id"] == "n1" and nodes[0]["op"] == "R"
    assert nodes[1]["id"] == "n2" and nodes[1]["op"] == "Err"


def test_retry_at_node_id_emits_retry_edge_from_that_node():
    """Retry @n1 2 100 produces a retry edge from n1 to the Retry node."""
    src = """
S core web /api
E /x G ->L1
L1: R api.G /x ->data Retry @n1 2 100 Set data 0 J data
"""
    c = AICodeCompiler()
    ir = c.compile(src)
    assert not ir.get("errors"), ir.get("errors")
    edges = ir["labels"]["1"]["edges"]
    retry_edges = [e for e in edges if e.get("port") == "retry"]
    assert len(retry_edges) == 1
    assert retry_edges[0]["from"] == "n1"
    assert retry_edges[0]["to"] == "n2"
    nodes = ir["labels"]["1"]["nodes"]
    assert nodes[0]["op"] == "R" and nodes[1]["op"] == "Retry"
