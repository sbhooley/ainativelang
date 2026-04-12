# pylint: disable=missing-module-docstring
import time

from compiler_v2 import AICodeCompiler, grammar_matches_token_class

TEST_PROVENANCE = AICodeCompiler()._emit_provenance_comment_block("#", "AINL pytest: test_semantic_edges")


def test_contradicts_edge_flags_both_nodes(tmp_path):
    from armaraos.bridge.ainl_graph_memory import EdgeType, GraphStore, MemoryEdge, MemoryNode, NodeType

    p = tmp_path / "g.json"
    p.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    store = GraphStore(path=p)
    now = time.time()
    a = MemoryNode(
        id="n_a",
        node_type=NodeType.SEMANTIC.value,
        agent_id="ag1",
        label="a",
        payload={"claim": "A"},
        tags=[],
        created_at=now,
    )
    b = MemoryNode(
        id="n_b",
        node_type=NodeType.SEMANTIC.value,
        agent_id="ag1",
        label="b",
        payload={"claim": "B"},
        tags=[],
        created_at=now,
    )
    store.add_node(a, persist=False)
    store.add_node(b, persist=False)
    e1 = MemoryEdge(id="e1", src="n_a", dst="n_b", edge_type=EdgeType.CONTRADICTS.value)
    store.add_edge(e1, persist=False)
    store.add_edge(e1, persist=False)
    na = store.get_node("n_a")
    nb = store.get_node("n_b")
    assert (na.payload.get("metadata") or {}).get("has_contradiction") is True
    assert (nb.payload.get("metadata") or {}).get("has_contradiction") is True
    assert "n_b" in (na.contradicted_by if na else [])
    assert "n_a" in (nb.contradicted_by if nb else [])
    assert na.contradicted_by.count("n_b") == 1


def test_believes_edge_stores_confidence(tmp_path):
    from armaraos.bridge.ainl_graph_memory import EdgeType, GraphStore, MemoryEdge, MemoryNode, NodeType

    p = tmp_path / "g2.json"
    p.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    store = GraphStore(path=p)
    now = time.time()
    ag = MemoryNode(
        id="agent1",
        node_type=NodeType.SEMANTIC.value,
        agent_id="ag1",
        label="agent",
        payload={},
        tags=[],
        created_at=now,
    )
    cn = MemoryNode(
        id="c1",
        node_type=NodeType.SEMANTIC.value,
        agent_id="ag1",
        label="c",
        payload={},
        tags=[],
        created_at=now,
    )
    store.add_node(ag, persist=False)
    store.add_node(cn, persist=False)
    edge = MemoryEdge(
        id="eb",
        src="agent1",
        dst="c1",
        edge_type=EdgeType.BELIEVES.value,
        meta={"confidence": 0.4},
    )
    out = store.add_edge(edge, persist=False)
    assert abs(out.confidence - 0.4) < 1e-9
    edges = store.all_edges()
    assert any(abs(e.confidence - 0.4) < 1e-9 for e in edges if e.id == "eb")


def test_edge_type_token_grammar():
    assert grammar_matches_token_class("EDGE_TYPE_TOKEN", "knows") is True
    assert grammar_matches_token_class("EDGE_TYPE_TOKEN", "invented_edge") is False


def test_compile_persona_update_emits_edge_type():
    code = """S app core noop
L1:
persona.update curiosity 0.8 learned_from
J 1
"""
    comp = AICodeCompiler(strict_mode=False, strict_reachability=False)
    ir = comp.compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    steps = ir["labels"]["1"]["legacy"]["steps"]
    assert steps[0]["op"] == "persona.update"
    assert steps[0].get("edge_type") == "learned_from"
