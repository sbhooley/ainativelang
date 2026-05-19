import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.pggraph.adapter import PggraphAdapter, validate_regclass
from runtime.adapters.base import AdapterError


class _RecordingPostgres:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list, dict]] = []

    def call(self, target: str, args: list, context: dict):
        self.calls.append((target, args, context))
        sql = str(args[0] if args else "")
        if "graph.test_enabled" in sql:
            return [{"enabled": True}]
        if "graph.status" in sql:
            return [{"node_count": 3, "edge_count": 2}]
        if "graph.search" in sql:
            return [{"node_id": "p1", "node_table_name": "public.people"}]
        if "graph.traverse" in sql:
            return [{"depth": 1, "node_id": "c1"}]
        if "graph.shortest_path" in sql:
            return [{"step": 0, "node_id": "p1"}]
        if "graph.find_related" in sql:
            return [{"depth": 1, "node_id": "p2"}]
        if "graph.build" in sql:
            return [{"nodes_loaded": 3}]
        if "graph.auto_discover" in sql:
            return [{"item_type": "table", "item_name": "people"}]
        if "graph.reset" in sql:
            return []
        return []


def _adapter(**kwargs) -> PggraphAdapter:
    return PggraphAdapter(_RecordingPostgres(), allow_admin=kwargs.pop("allow_admin", False), **kwargs)


def test_validate_regclass():
    assert validate_regclass("people") == "public.people"
    assert validate_regclass("bookings.flights") == "bookings.flights"
    with pytest.raises(AdapterError):
        validate_regclass("bad-name!")


def test_pggraph_test_enabled_and_status():
    pg = _RecordingPostgres()
    adp = PggraphAdapter(pg)
    out = adp.call("test_enabled", [], {})
    assert out["enabled"] is True
    rows = adp.call("status", [], {})
    assert rows[0]["node_count"] == 3
    assert pg.calls[0][0] == "query"
    assert "graph.test_enabled" in pg.calls[0][1][0]


def test_pggraph_search_traverse_shortest_path():
    adp = _adapter()
    adp.call("search", ["name", "Alice", "people"], {})
    adp.call("traverse", ["public.people", "p1", 2, False], {})
    adp.call("shortest_path", ["people", "p1", "companies", "c1"], {})
    adp.call("find_related", ["name", "Bob", "people"], {})


def test_pggraph_admin_blocked_by_default():
    adp = _adapter(allow_admin=False)
    with pytest.raises(AdapterError) as exc:
        adp.call("build", [], {})
    assert "allow_admin" in str(exc.value)


def test_pggraph_admin_when_enabled():
    adp = _adapter(allow_admin=True)
    adp.call("build", [], {})
    adp.call("auto_discover", ["public"], {})
    out = adp.call("reset", [], {})
    assert out == {"ok": True}


def test_pggraph_rejects_unknown_verb():
    adp = _adapter()
    with pytest.raises(AdapterError):
        adp.call("dijkstra", [], {})


def test_suggested_mcp_adapters_payload_includes_pggraph():
    from scripts.ainl_mcp_server import _suggested_adapters_payload

    payload = _suggested_adapters_payload(["pggraph"], ir={})
    assert payload["enable"] == ["pggraph"]
    assert "url" in payload["pggraph"]
