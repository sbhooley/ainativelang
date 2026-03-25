"""embedding_memory adapter (stub embeddings + cosine search)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.embedding_memory import EmbeddingMemoryAdapter


def test_embedding_memory_stub_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "emb.sqlite3"
    monkeypatch.setenv("AINL_EMBEDDING_MEMORY_DB", str(db))
    monkeypatch.setenv("AINL_EMBEDDING_MODE", "stub")

    a = EmbeddingMemoryAdapter()
    a.call("UPSERT_REF", ["session", "note", "a", "openclaw token budget weekly rollup"], {})
    a.call("UPSERT_REF", ["session", "note", "b", "pasta carbonara dinner recipe"], {})

    hits = a.call("SEARCH", ["openclaw token budget", 5], {})
    assert isinstance(hits, list)
    assert len(hits) >= 1
    assert hits[0]["memory_record_id"] == "a"

    a.call("REMOVE_REF", ["session", "note", "a"], {})
    hits2 = a.call("SEARCH", ["openclaw", 5], {})
    ids = {h["memory_record_id"] for h in hits2}
    assert "a" not in ids
