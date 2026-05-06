"""Dedicated coverage for ``tooling/effect_analysis.py``.

The module sees high churn (30+ commits in 90 days at the time of writing)
and was previously exercised only incidentally through compiler / fixture
tests. This file pins the public contract of:

- the ``ADAPTER_EFFECT`` allowlist (shape and constant invariants)
- ``strict_adapter_key`` / ``strict_adapter_key_for_step`` / ``strict_adapter_is_allowed`` / ``strict_adapter_effect``
- ``effect_tier_for_node`` / ``effect_kinds_for_node`` (op-by-op dispatch)
- ``compute_label_effect_summary`` / ``annotate_label_with_effect_summary`` / ``annotate_ir_effect_analysis`` / ``annotate_labels_effect_analysis``
- ``forward_dataflow_defs`` / ``propagate_inter_label_entry_defs`` / ``dataflow_defined_before_use``

Refs: sbhooley/ainativelang#39 P1-9 (effect_analysis coverage gap).
"""
from __future__ import annotations

from typing import Any, Optional

import pytest

from tooling import effect_analysis as ea
from tooling.effect_analysis import (
    ADAPTER_EFFECT,
    EFFECT_KIND_CACHE_READ,
    EFFECT_KIND_CACHE_WRITE,
    EFFECT_KIND_CALL,
    EFFECT_KIND_COMPUTE,
    EFFECT_KIND_CONTROL,
    EFFECT_KIND_DB_READ,
    EFFECT_KIND_DB_WRITE,
    EFFECT_KIND_FS,
    EFFECT_KIND_HTTP,
    EFFECT_KIND_MEMORY_READ,
    EFFECT_KIND_MEMORY_WRITE,
    EFFECT_KIND_META,
    EFFECT_KIND_QUEUE,
    EFFECT_KIND_SQLITE,
    EFFECT_KIND_TOOL,
    EFFECT_KIND_TXN,
    EFFECT_TIER_CONTROL,
    EFFECT_TIER_IO_READ,
    EFFECT_TIER_IO_WRITE,
    EFFECT_TIER_META,
    EFFECT_TIER_PURE,
    PREDEFINED_VARS,
    annotate_ir_effect_analysis,
    annotate_label_with_effect_summary,
    annotate_labels_effect_analysis,
    compute_label_effect_summary,
    dataflow_defined_before_use,
    effect_kinds_for_node,
    effect_tier_for_node,
    forward_dataflow_defs,
    propagate_inter_label_entry_defs,
    strict_adapter_effect,
    strict_adapter_is_allowed,
    strict_adapter_key,
    strict_adapter_key_for_step,
)


# --- ADAPTER_EFFECT map invariants -----------------------------------------


_VALID_TIERS = {
    EFFECT_TIER_PURE,
    EFFECT_TIER_IO_READ,
    EFFECT_TIER_IO_WRITE,
    EFFECT_TIER_CONTROL,
    EFFECT_TIER_META,
}

_VALID_KINDS = {
    EFFECT_KIND_DB_READ,
    EFFECT_KIND_DB_WRITE,
    EFFECT_KIND_HTTP,
    EFFECT_KIND_CACHE_READ,
    EFFECT_KIND_CACHE_WRITE,
    EFFECT_KIND_QUEUE,
    EFFECT_KIND_TXN,
    EFFECT_KIND_SQLITE,
    EFFECT_KIND_FS,
    EFFECT_KIND_MEMORY_READ,
    EFFECT_KIND_MEMORY_WRITE,
    EFFECT_KIND_TOOL,
    EFFECT_KIND_CALL,
    EFFECT_KIND_CONTROL,
    EFFECT_KIND_META,
    EFFECT_KIND_COMPUTE,
}


def test_adapter_effect_keys_use_namespace_dot_uppercase_verb_shape():
    """Every key must be ``<namespace>.<VERB>`` with the verb uppercased so
    callers can rely on ``strict_adapter_key`` producing matching keys."""
    for key in ADAPTER_EFFECT:
        assert "." in key, f"ADAPTER_EFFECT key must be dotted: {key!r}"
        ns, verb = key.split(".", 1)
        assert ns, f"namespace empty in {key!r}"
        assert verb, f"verb empty in {key!r}"
        assert verb == verb.upper(), f"verb must be uppercased: {key!r}"


def test_adapter_effect_values_are_tier_kind_pairs_using_known_constants():
    for key, value in ADAPTER_EFFECT.items():
        assert isinstance(value, tuple) and len(value) == 2, f"{key!r} -> {value!r}"
        tier, kind = value
        assert tier in _VALID_TIERS, f"{key!r} unknown tier {tier!r}"
        assert kind in _VALID_KINDS, f"{key!r} unknown kind {kind!r}"


def test_adapter_effect_pure_tier_implies_compute_kind():
    """Pure tier is reserved for deterministic compute helpers; mixing it
    with an io kind would silently mis-classify an effectful op."""
    for key, (tier, kind) in ADAPTER_EFFECT.items():
        if tier == EFFECT_TIER_PURE:
            assert kind == EFFECT_KIND_COMPUTE, (
                f"{key!r} pure tier should pair with compute kind, got {kind!r}"
            )


# --- strict_adapter_key and friends ----------------------------------------


def test_strict_adapter_key_dotted_input_uppercases_verb():
    assert strict_adapter_key("http.get") == "http.GET"
    assert strict_adapter_key("HTTP.get") == "HTTP.GET"
    assert strict_adapter_key("supabase.realtime_subscribe") == "supabase.REALTIME_SUBSCRIBE"


def test_strict_adapter_key_undotted_uses_req_op():
    assert strict_adapter_key("db", "f") == "db.F"
    assert strict_adapter_key("db", "F") == "db.F"


def test_strict_adapter_key_undotted_no_req_op_defaults_to_F():
    """Historic compatibility default: bare adapter without verb routes to F."""
    assert strict_adapter_key("db") == "db.F"


def test_strict_adapter_key_empty_adapter_returns_empty_string():
    assert strict_adapter_key("") == ""
    assert strict_adapter_key(None) == ""


def test_strict_adapter_key_for_step_dispatches_special_op_aliases():
    """Compiler-internal op names route to canonical adapter.VERB keys."""
    assert strict_adapter_key_for_step({"op": "memory.merge"}) == "memory.MERGE"
    assert strict_adapter_key_for_step({"op": "MemoryMerge"}) == "memory.MERGE"
    assert strict_adapter_key_for_step({"op": "MemoryExecute"}) == "ainl_graph_memory.MEMORY_EXECUTE"
    assert strict_adapter_key_for_step({"op": "MemoryPatch"}) == "ainl_graph_memory.MEMORY_PATCH"
    assert strict_adapter_key_for_step({"op": "persona.update"}) == "persona.UPDATE"


def test_strict_adapter_key_for_step_normal_adapter_with_req_op():
    step = {"adapter": "db", "req_op": "g"}
    assert strict_adapter_key_for_step(step) == "db.G"


def test_strict_adapter_key_for_step_falls_back_to_entity_when_req_op_missing():
    """``R adapter verb args`` IR nodes leave req_op empty and put the verb
    in entity; the resolver must still produce the real verb, not the
    sentinel ``F``."""
    step = {"adapter": "http", "entity": "POST"}
    assert strict_adapter_key_for_step(step) == "http.POST"
    step2 = {"adapter": "http", "target": "GET"}
    assert strict_adapter_key_for_step(step2) == "http.GET"


def test_strict_adapter_key_for_step_dotted_adapter_passes_through():
    step = {"adapter": "supabase.SELECT"}
    assert strict_adapter_key_for_step(step) == "supabase.SELECT"


def test_strict_adapter_key_for_step_uses_src_when_adapter_missing():
    step = {"src": "fs", "req_op": "READ"}
    assert strict_adapter_key_for_step(step) == "fs.READ"


def test_strict_adapter_is_allowed_known_keys():
    assert strict_adapter_is_allowed("http.GET") is True
    assert strict_adapter_is_allowed("core.ADD") is True


def test_strict_adapter_is_allowed_rejects_unknown_and_empty():
    assert strict_adapter_is_allowed("foo.BAR") is False
    assert strict_adapter_is_allowed("") is False


def test_strict_adapter_effect_returns_tuple_or_none():
    assert strict_adapter_effect("http.GET") == (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP)
    assert strict_adapter_effect("nonexistent.X") is None


# --- effect_tier_for_node / effect_kinds_for_node --------------------------


def test_effect_tier_for_node_err_is_meta():
    assert effect_tier_for_node({"op": "Err"}) == EFFECT_TIER_META


def test_effect_tier_for_node_retry_is_control():
    assert effect_tier_for_node({"op": "Retry"}) == EFFECT_TIER_CONTROL


def test_effect_tier_for_node_R_uses_adapter_effect():
    node = {"op": "R", "data": {"adapter": "http", "req_op": "GET"}}
    assert effect_tier_for_node(node) == EFFECT_TIER_IO_READ


def test_effect_tier_for_node_R_unknown_adapter_falls_back_to_io_write():
    """Conservative default: an unknown adapter is treated as a write so
    planning/safety errs on the side of caution."""
    node = {"op": "R", "data": {"adapter": "completely_unknown", "req_op": "DO"}}
    assert effect_tier_for_node(node) == EFFECT_TIER_IO_WRITE


def test_effect_tier_for_node_call_and_writes_are_io_write():
    for op in ("Call", "QueuePut", "CacheSet", "Tx"):
        assert effect_tier_for_node({"op": op}) == EFFECT_TIER_IO_WRITE


def test_effect_tier_for_node_cache_get_is_io_read():
    assert effect_tier_for_node({"op": "CacheGet"}) == EFFECT_TIER_IO_READ


def test_effect_tier_for_node_memory_recall_search_execute_are_io_read():
    for op in ("MemoryRecall", "MemorySearch", "MemoryExecute"):
        assert effect_tier_for_node({"op": op}) == EFFECT_TIER_IO_READ


def test_effect_tier_for_node_persona_update_and_memory_patch_are_io_write():
    assert effect_tier_for_node({"op": "persona.update"}) == EFFECT_TIER_IO_WRITE
    assert effect_tier_for_node({"op": "MemoryPatch"}) == EFFECT_TIER_IO_WRITE


def test_effect_tier_for_node_control_ops():
    for op in ("If", "Loop", "While"):
        assert effect_tier_for_node({"op": op}) == EFFECT_TIER_CONTROL


def test_effect_tier_for_node_unknown_op_defaults_to_pure():
    assert effect_tier_for_node({"op": "MysteryOp"}) == EFFECT_TIER_PURE


def test_effect_kinds_for_node_R_uses_adapter_kind():
    node = {"op": "R", "data": {"adapter": "fs", "req_op": "READ"}}
    assert effect_kinds_for_node(node) == {EFFECT_KIND_FS}


def test_effect_kinds_for_node_specials():
    assert effect_kinds_for_node({"op": "Err"}) == {EFFECT_KIND_META}
    assert effect_kinds_for_node({"op": "Retry"}) == {EFFECT_KIND_CONTROL}
    assert effect_kinds_for_node({"op": "Call"}) == {EFFECT_KIND_CALL}
    assert effect_kinds_for_node({"op": "CacheGet"}) == {EFFECT_KIND_CACHE_READ}
    assert effect_kinds_for_node({"op": "CacheSet"}) == {EFFECT_KIND_CACHE_WRITE}
    assert effect_kinds_for_node({"op": "QueuePut"}) == {EFFECT_KIND_QUEUE}
    assert effect_kinds_for_node({"op": "Tx"}) == {EFFECT_KIND_TXN}
    assert effect_kinds_for_node({"op": "MemoryRecall"}) == {EFFECT_KIND_MEMORY_READ}
    assert effect_kinds_for_node({"op": "MemoryPatch"}) == {EFFECT_KIND_MEMORY_WRITE}


def test_effect_kinds_for_node_unknown_op_returns_empty_set():
    assert effect_kinds_for_node({"op": "MysteryOp"}) == set()


# --- label and IR annotation -----------------------------------------------


def _node(nid: str, op: str, *, reads=None, writes=None, **extra) -> dict:
    n = {"id": nid, "op": op, "reads": list(reads or []), "writes": list(writes or [])}
    n.update(extra)
    return n


def test_compute_label_effect_summary_aggregates_reads_writes_effects():
    nodes = [
        _node("a", "CacheGet", reads=["k1"], writes=["v1"]),
        _node("b", "QueuePut", reads=["v1"], writes=["msg"]),
        _node("c", "MemoryRecall", reads=["q"]),
    ]
    summary = compute_label_effect_summary(nodes, edges=[], entry="a")
    assert summary["reads"] == ["k1", "q", "v1"]  # sorted
    assert summary["writes"] == ["msg", "v1"]
    assert set(summary["effects"]) == {
        EFFECT_KIND_CACHE_READ,
        EFFECT_KIND_QUEUE,
        EFFECT_KIND_MEMORY_READ,
    }


def test_annotate_label_with_effect_summary_adds_per_node_fields():
    label = {
        "entry": "a",
        "nodes": [_node("a", "R", data={"adapter": "http", "req_op": "GET"})],
        "edges": [],
    }
    out = annotate_label_with_effect_summary(label)
    assert out["nodes"][0]["effect_tier"] == EFFECT_TIER_IO_READ
    assert out["nodes"][0]["effect_kinds"] == [EFFECT_KIND_HTTP]
    assert out["effect_summary"]["effects"] == [EFFECT_KIND_HTTP]
    # Input must not be mutated.
    assert "effect_tier" not in label["nodes"][0]


def test_annotate_label_with_effect_summary_empty_nodes_yields_empty_summary():
    out = annotate_label_with_effect_summary({"entry": None, "nodes": [], "edges": []})
    assert out["effect_summary"] == {"reads": [], "writes": [], "effects": []}


def test_annotate_ir_effect_analysis_annotates_every_label_and_deep_copies():
    ir = {
        "labels": {
            "1": {
                "entry": "a",
                "nodes": [_node("a", "CacheGet", reads=["k"])],
                "edges": [],
            },
            "2": {
                "entry": "b",
                "nodes": [_node("b", "QueuePut", writes=["m"])],
                "edges": [],
            },
        }
    }
    out = annotate_ir_effect_analysis(ir)
    assert out["labels"]["1"]["nodes"][0]["effect_tier"] == EFFECT_TIER_IO_READ
    assert out["labels"]["2"]["nodes"][0]["effect_tier"] == EFFECT_TIER_IO_WRITE
    # Input is deep-copied.
    assert "effect_tier" not in ir["labels"]["1"]["nodes"][0]
    assert ir["labels"]["1"] is not out["labels"]["1"]


def test_annotate_labels_effect_analysis_mutates_in_place():
    labels = {
        "1": {
            "entry": "a",
            "nodes": [_node("a", "MemoryPatch", writes=["m"])],
            "edges": [],
        }
    }
    annotate_labels_effect_analysis(labels)
    assert labels["1"]["nodes"][0]["effect_tier"] == EFFECT_TIER_IO_WRITE
    assert labels["1"]["effect_summary"]["effects"] == [EFFECT_KIND_MEMORY_WRITE]


# --- intra-label dataflow --------------------------------------------------


def test_forward_dataflow_defs_simple_chain_propagates_writes_forward():
    nodes = [
        _node("a", "X", writes=["x"]),
        _node("b", "Y", writes=["y"]),
        _node("c", "Z"),
    ]
    edges = [
        {"from": "a", "to": "b", "to_kind": "node", "port": "next"},
        {"from": "b", "to": "c", "to_kind": "node", "port": "next"},
    ]
    defs = forward_dataflow_defs(nodes, edges, entry="a")
    assert defs["a"] == {"x"}
    assert defs["b"] == {"x", "y"}
    assert defs["c"] == {"x", "y"}


def test_forward_dataflow_defs_seed_entry_defined_is_visible_at_entry():
    nodes = [_node("a", "X")]
    defs = forward_dataflow_defs(nodes, edges=[], entry="a", entry_defined={"seed"})
    assert "seed" in defs["a"]


def test_forward_dataflow_defs_branch_intersection_is_union_of_paths():
    """If two paths both reach a node, defined_at[node] is the union of
    each path's defs (not intersection) -- matches the module's "vars
    defined on at least one path" contract."""
    nodes = [
        _node("a", "X"),
        _node("b1", "Y", writes=["b1var"]),
        _node("b2", "Z", writes=["b2var"]),
        _node("c", "W"),
    ]
    edges = [
        {"from": "a", "to": "b1", "to_kind": "node", "port": "then"},
        {"from": "a", "to": "b2", "to_kind": "node", "port": "else"},
        {"from": "b1", "to": "c", "to_kind": "node", "port": "next"},
        {"from": "b2", "to": "c", "to_kind": "node", "port": "next"},
    ]
    defs = forward_dataflow_defs(nodes, edges, entry="a")
    assert defs["c"] == {"b1var", "b2var"}


def test_forward_dataflow_defs_ignores_cross_label_edges():
    nodes = [_node("a", "X", writes=["x"]), _node("b", "Y")]
    edges = [
        {"from": "a", "to": "OtherLabel", "to_kind": "label", "port": "next"},
        {"from": "a", "to": "b", "to_kind": "node", "port": "next"},
    ]
    defs = forward_dataflow_defs(nodes, edges, entry="a")
    assert defs["b"] == {"x"}  # cross-label edge ignored, intra-label intact


def test_forward_dataflow_defs_skips_failure_ports():
    """Only success ports (next/then/else/body/after) propagate intra-label
    defs forward; an ``err`` port should not."""
    nodes = [
        _node("a", "X", writes=["x"]),
        _node("b", "Y"),
    ]
    edges = [
        {"from": "a", "to": "b", "to_kind": "node", "port": "err"},
    ]
    defs = forward_dataflow_defs(nodes, edges, entry="a")
    # b has no success-port predecessor and is not entry, so it's not in defs.
    assert "b" not in defs


def test_dataflow_defined_before_use_flags_unseeded_reads():
    nodes = [
        _node("a", "X", reads=["never_defined"], writes=[]),
    ]
    violations = dataflow_defined_before_use(nodes, edges=[], entry="a")
    assert violations == [("a", "never_defined")]


def test_dataflow_defined_before_use_does_not_flag_predefined_vars():
    """``PREDEFINED_VARS`` are conventionally defined by runtime/wiring."""
    sample = next(iter(PREDEFINED_VARS))
    nodes = [_node("a", "X", reads=[sample])]
    assert dataflow_defined_before_use(nodes, edges=[], entry="a") == []


def test_dataflow_defined_before_use_clean_when_writes_precede_reads():
    nodes = [
        _node("a", "X", writes=["x"]),
        _node("b", "Y", reads=["x"]),
    ]
    edges = [{"from": "a", "to": "b", "to_kind": "node", "port": "next"}]
    assert dataflow_defined_before_use(nodes, edges, entry="a") == []


# --- inter-label propagation -----------------------------------------------


def _norm_lid(lid: Any) -> Optional[str]:
    """Trivial normalizer matching the compiler's numeric-label keying."""
    if lid is None:
        return None
    return str(lid)


def test_propagate_inter_label_entry_defs_propagates_live_vars_across_labels():
    labels = {
        "1": {
            "entry": "a",
            "nodes": [_node("a", "X", writes=["live"])],
            "edges": [
                {"from": "a", "to": "2", "to_kind": "label", "port": "next"},
            ],
        },
        "2": {
            "entry": "b",
            "nodes": [_node("b", "Y")],
            "edges": [],
        },
    }
    out = propagate_inter_label_entry_defs(labels, norm_lid=_norm_lid)
    assert "live" in out["2"], f"expected 'live' propagated to label 2, got {out!r}"


def test_propagate_inter_label_entry_defs_seeds_endpoint_entry_defs():
    labels = {
        "1": {"entry": "a", "nodes": [_node("a", "X")], "edges": []},
    }
    out = propagate_inter_label_entry_defs(
        labels,
        norm_lid=_norm_lid,
        endpoint_entry_defs={"1": {"http_payload"}},
    )
    assert out["1"] == {"http_payload"}


# --- module-level constants ------------------------------------------------


def test_predefined_vars_contains_documented_runtime_conventions():
    """Pin the set of vars callers can rely on as always-defined."""
    expected = {"_auth_present", "_role", "_error", "_call_result", "_loop_last", "_while_last", "_txid"}
    assert PREDEFINED_VARS == expected
