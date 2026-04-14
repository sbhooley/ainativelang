"""Tests for ``armaraos.bridge.ainl_memory_sync``."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

# Repo root: armaraos/bridge/tests -> armaraos -> AI_Native_Lang
_REPO_ROOT = Path(__file__).resolve().parents[2].parent
import sys

sys.path.insert(0, str(_REPO_ROOT))


def test_push_nodes_writes_inbox_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from armaraos.bridge.ainl_graph_memory import MemoryNode, NodeType
    from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter, INBOX_FILENAME

    agent_id = "agent_test_1"
    home = tmp_path / "home"
    (home / "agents").mkdir(parents=True)
    monkeypatch.setenv("ARMARAOS_AGENT_ID", agent_id)
    monkeypatch.setenv("ARMARAOS_HOME", str(home))

    node = MemoryNode(
        id="epi_test_1",
        node_type=NodeType.EPISODIC.value,
        agent_id=agent_id,
        label="unit",
        payload={"k": 1},
        tags=["t"],
        created_at=123.0,
        ttl=None,
    )
    w = AinlMemorySyncWriter()
    assert w.is_available() is True
    res = w.push_nodes([node])
    assert res.error is None
    assert res.pushed == 1
    inbox = home / "agents" / agent_id / INBOX_FILENAME
    assert inbox.is_file()
    data = json.loads(inbox.read_text(encoding="utf-8"))
    assert isinstance(data.get("nodes"), list)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "epi_test_1"
    assert data["nodes"][0]["node_type"] == "episodic"
    assert isinstance(data.get("edges"), list)


def test_push_nodes_no_op_when_agent_id_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from armaraos.bridge.ainl_graph_memory import MemoryNode, NodeType
    from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter

    monkeypatch.delenv("ARMARAOS_AGENT_ID", raising=False)
    monkeypatch.setenv("ARMARAOS_HOME", str(tmp_path / "home"))

    node = MemoryNode(
        id="n1",
        node_type=NodeType.EPISODIC.value,
        agent_id="x",
        label="l",
        payload={},
        tags=[],
        created_at=1.0,
        ttl=None,
    )
    w = AinlMemorySyncWriter()
    assert w.is_available() is False
    res = w.push_nodes([node])
    assert res.pushed == 0
    assert res.skipped == 0
    assert res.error == "sync_unavailable"
    assert not list(tmp_path.rglob("ainl_graph_memory_inbox.json"))


def test_inbox_atomic_replace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from armaraos.bridge.ainl_graph_memory import MemoryNode, NodeType
    from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter

    agent_id = "agent_conc"
    home = tmp_path / "h"
    (home / "agents").mkdir(parents=True)
    monkeypatch.setenv("ARMARAOS_AGENT_ID", agent_id)
    monkeypatch.setenv("ARMARAOS_HOME", str(home))

    w = AinlMemorySyncWriter()
    barrier = threading.Barrier(8)

    def worker(i: int) -> None:
        barrier.wait()
        n = MemoryNode(
            id=f"node_{i}",
            node_type=NodeType.EPISODIC.value,
            agent_id=agent_id,
            label="c",
            payload={"i": i},
            tags=[],
            created_at=float(i),
            ttl=None,
        )
        w.push_nodes([n])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    inbox = w._inbox_path
    assert inbox is not None
    raw = inbox.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert isinstance(data.get("nodes"), list)
    assert len(data["nodes"]) == 8
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {f"node_{i}" for i in range(8)}
