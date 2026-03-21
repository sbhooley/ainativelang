"""
demo/session_budget_enforcer.lang — access-aware wiring and metadata contract.

We assert the demo compiles with merged `accmem` labels (includes before `S`) and
validate `last_accessed` / `access_count` behavior with the same adapter sequence
`LACCESS_READ` would perform (get → merge meta → put). Graph mode also resolves
bare child label ids under an include-style prefix (see
``test_graph_mode_nested_if_resolves_bare_child_labels``).
The demo still calls ``accmem/LACCESS_LIST`` for compile coverage; nested list
touches may be incomplete in graph-preferred mode—use ``LACCESS_LIST_SAFE`` in
production when full per-item access updates are required (see
``modules/common/access_aware_memory.ainl`` header).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402
from runtime.adapters.memory import MemoryAdapter  # noqa: E402
from runtime.adapters.builtins import CoreBuiltinAdapter  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402
from runtime.adapters.base import AdapterRegistry  # noqa: E402


def _touch_like_laccess_read(adp: MemoryAdapter, ns: str, kind: str, rid: str) -> None:
    got = adp.call("get", [ns, kind, rid], {})
    assert got.get("found") is True
    rec = got["record"]
    payload = rec["payload"]
    ttl = rec["ttl_seconds"]
    meta = dict(rec.get("metadata") or {})
    meta["last_accessed"] = datetime.now(timezone.utc).isoformat()
    prev = meta.get("access_count")
    meta["access_count"] = 1 if prev is None else int(prev) + 1
    adp.call("put", [ns, kind, rid, payload, ttl, meta], {})


def test_session_budget_enforcer_compiles_with_access_aware_includes(tmp_path: Path) -> None:
    demo_path = ROOT / "demo" / "session_budget_enforcer.lang"
    demo = demo_path.read_text(encoding="utf-8")
    assert "Call accmem/LACCESS_LIST" in demo
    assert "workflow.budget_enforcement" in demo
    # Prelude: include lines must appear before `S` so modules merge into IR.
    inc_tok = demo.index('include "modules/common/token_cost_memory.ainl"')
    inc_acc = demo.index('include "modules/common/access_aware_memory.ainl"')
    s_line = demo.index('S http cron')
    assert inc_tok < s_line and inc_acc < s_line

    ir = AICodeCompiler(strict_mode=False).compile(demo, source_path=str(demo_path), emit_graph=True)
    assert not ir.get("errors")
    labels = ir.get("labels") or {}
    assert any("accmem" in k and "ACCESS_LIST" in k.upper() for k in labels)
    assert any("tokenmem" in k and "WRITE" in k.upper() for k in labels)

    db = str(tmp_path / "enforcer_access.sqlite3")
    mem = MemoryAdapter(db_path=db)
    mem.call(
        "put",
        [
            "workflow",
            "workflow.budget_enforcement",
            "preseed-audit",
            {"gate": "normal", "daily_used": 0.1, "ts": 1},
            604800,
            {
                "source": "demo.session_budget_enforcer",
                "tags": ["budget", "enforcement"],
                "valid_at": "2026-01-01T00:00:00+00:00",
            },
        ],
        {},
    )
    _touch_like_laccess_read(mem, "workflow", "workflow.budget_enforcement", "preseed-audit")

    got = mem.call("get", ["workflow", "workflow.budget_enforcement", "preseed-audit"], {})
    assert got.get("found") is True
    meta = (got.get("record") or {}).get("metadata") or {}
    la = meta.get("last_accessed")
    ac = meta.get("access_count")
    assert la and isinstance(ac, int) and ac >= 1
    assert "T" in str(la)
    parsed = datetime.fromisoformat(str(la).replace("Z", "+00:00"))
    assert (datetime.now(timezone.utc) - parsed).total_seconds() < 300


def test_graph_mode_nested_if_resolves_bare_child_labels() -> None:
    """Bare ``to_kind=label`` edge targets match ``alias/name`` keys after includes."""
    ir = {
        "ir_version": "1.0",
        "labels": {
            "m/PARENT": {
                "entry": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "op": "Set",
                        "data": {"op": "Set", "lineno": 1, "name": "cond", "ref": True},
                    },
                    {
                        "id": "n2",
                        "op": "If",
                        "data": {"op": "If", "lineno": 2, "cond": "cond", "then": "_c", "else": "_z"},
                    },
                ],
                "edges": [
                    {"from": "n1", "to": "n2", "to_kind": "node", "port": "next"},
                    {"from": "n2", "to": "_c", "to_kind": "label", "port": "then"},
                    {"from": "n2", "to": "_z", "to_kind": "label", "port": "else"},
                ],
                "legacy": {"steps": []},
            },
            "m/_c": {
                "entry": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "op": "Set",
                        "data": {"op": "Set", "lineno": 1, "name": "branch_hit", "ref": "then"},
                    },
                    {"id": "n2", "op": "J", "data": {"op": "J", "lineno": 2, "var": "branch_hit"}},
                ],
                "edges": [{"from": "n1", "to": "n2", "to_kind": "node", "port": "next"}],
                "legacy": {"steps": []},
            },
            "m/_z": {
                "entry": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "op": "Set",
                        "data": {"op": "Set", "lineno": 1, "name": "branch_hit", "ref": "else"},
                    },
                ],
                "edges": [],
                "legacy": {"steps": []},
            },
        },
        "services": {},
        "capabilities": {},
        "runtime_policy": {},
    }
    reg = AdapterRegistry(allowed=["core"])
    reg.register("core", CoreBuiltinAdapter())
    eng = RuntimeEngine(ir, adapters=reg, trace=False, step_fallback=False, execution_mode="graph-only")
    # run_label copies the frame; nested label side effects live on the engine-internal copy.
    out = eng.run_label("m/PARENT", {})
    assert out == "then"
