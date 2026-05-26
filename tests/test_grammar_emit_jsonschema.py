"""
Tests for tooling.grammar_emit_jsonschema — JSON Schema and EBNF emission.
"""
import json
import pytest

from tooling.grammar_emit_jsonschema import emit_jsonschema, emit_ebnf


def test_emit_jsonschema_returns_valid_schema():
    schema = emit_jsonschema()
    assert schema["type"] == "string"
    assert schema["minLength"] > 0
    assert schema["maxLength"] > 0
    assert "metadata" in schema
    meta = schema["metadata"]
    assert "adapter_names" in meta
    assert isinstance(meta["adapter_names"], list)
    assert "core" not in meta["adapter_names"] or len(meta["adapter_names"]) > 1


def test_emit_jsonschema_metadata_includes_ops():
    schema = emit_jsonschema()
    meta = schema["metadata"]
    assert "top_level_ops" in meta
    assert "label_ops" in meta
    assert "R" in meta["label_ops"]
    assert "J" in meta["label_ops"]
    assert "Set" in meta["label_ops"]


def test_emit_jsonschema_serializable():
    schema = emit_jsonschema()
    serialized = json.dumps(schema)
    roundtrip = json.loads(serialized)
    assert roundtrip == schema


def test_emit_ebnf_produces_valid_ebnf():
    ebnf = emit_ebnf()
    assert len(ebnf) > 100
    assert "program" in ebnf
    assert "label_header" in ebnf
    assert "compact_header" in ebnf
    assert "adapter_call" in ebnf
    assert "r_line" in ebnf


def test_emit_ebnf_deterministic():
    e1 = emit_ebnf()
    e2 = emit_ebnf()
    assert e1 == e2
