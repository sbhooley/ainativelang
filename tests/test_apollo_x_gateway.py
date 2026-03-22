"""Integration: apollo-x-bot gateway + ainl-x-promoter.ainl with ExecutorBridgeAdapter."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apollo-x-bot"))
import gateway_server as gw  # noqa: E402

from runtime.adapters.builtins import CoreBuiltinAdapter  # noqa: E402
from runtime.adapters.executor_bridge import ExecutorBridgeAdapter  # noqa: E402
from runtime.adapters.base import AdapterRegistry  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402


def _serve_gateway(state_path: Path) -> ThreadingHTTPServer:
    gw._STATE = gw.PromoterState(state_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), gw.GatewayHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _registry(port: int) -> AdapterRegistry:
    base = f"http://127.0.0.1:{port}"
    endpoints = {
        "x.search": f"{base}/v1/x.search",
        "llm.classify": f"{base}/v1/llm.classify",
        "llm.json_array_extract": f"{base}/v1/llm.json_array_extract",
        "llm.merge_classify_rows": f"{base}/v1/llm.merge_classify_rows",
        "promoter.text_contains_any": f"{base}/v1/promoter.text_contains_any",
        "promoter.heuristic_scores": f"{base}/v1/promoter.heuristic_scores",
        "promoter.classify_prompts": f"{base}/v1/promoter.classify_prompts",
        "promoter.gate_eval": f"{base}/v1/promoter.gate_eval",
        "promoter.process_tweet": f"{base}/v1/promoter.process_tweet",
        "promoter.search_cursor_commit": f"{base}/v1/promoter.search_cursor_commit",
        "promoter.maybe_daily_post": f"{base}/v1/promoter.maybe_daily_post",
    }
    r = AdapterRegistry(allowed=["core", "bridge"])
    r.register("core", CoreBuiltinAdapter())
    r.register("bridge", ExecutorBridgeAdapter(endpoints=endpoints, default_timeout_s=120.0))
    return r


def test_promoter_graph_runs_with_gateway_dry_run():
    fd, tmp = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.unlink(tmp)
    state_path = Path(tmp)

    old = os.environ.get("PROMOTER_DRY_RUN")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    os.environ["PROMOTER_STATE_PATH"] = str(state_path)
    httpd: ThreadingHTTPServer | None = None
    try:
        httpd = _serve_gateway(state_path)
        port = httpd.server_port
        code = (ROOT / "apollo-x-bot/ainl-x-promoter.ainl").read_text(encoding="utf-8")
        eng = RuntimeEngine.from_code(
            code,
            strict=True,
            adapters=_registry(port),
            source_path=str(ROOT / "apollo-x-bot/ainl-x-promoter.ainl"),
        )
        out = eng.run_label("_poll", frame={})
        assert out == "ok"
    finally:
        if old is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old
        os.environ.pop("PROMOTER_STATE_PATH", None)
        if state_path.exists():
            state_path.unlink()
        if httpd is not None:
            httpd.shutdown()


def test_gateway_llm_json_array_extract_and_merge(tmp_path):
    state_path = tmp_path / "st.sqlite"
    gw._STATE = gw.PromoterState(state_path)
    out = gw.handle_llm_json_array_extract({"text": 'prefix [{"id":"1","score":7}] suffix'}, gw._STATE)
    assert out["ok"] is True
    assert isinstance(out["array"], list) and out["array"][0]["id"] == "1"

    tweets = [{"id": "1", "text": "hi"}]
    rows = [{"score": 8, "why": "ok"}]
    merged = gw.handle_llm_merge_classify_rows({"tweets": tweets, "score_rows": rows}, gw._STATE)
    assert merged["items"][0]["id"] == "1"
    assert merged["items"][0]["score"] == 8.0
    assert merged["items"][0]["why"] == "ok"


def test_gateway_llm_classify_legacy_list_shape(tmp_path):
    """Default classify (no envelope flags) still returns a JSON list for FILTER_HIGH_SCORE."""
    state_path = tmp_path / "st.sqlite"
    gw._STATE = gw.PromoterState(state_path)
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    try:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        out = gw.handle_llm_classify(
            {"tweets": [{"id": "a", "text": "OpenClaw orchestration"}]},
            gw._STATE,
        )
        assert isinstance(out, list)
        assert out[0]["id"] == "a"
        assert float(out[0]["score"]) >= 1.0
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry


def test_gateway_text_contains_any_and_gate_eval(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    h = gw.handle_text_contains_any(
        {"haystack": "OpenClaw and graphs", "phrases": ["openclaw", "nope"]},
        st,
    )
    assert h["hit_count"] == 1
    assert h["any"] is True
    g = gw.handle_promoter_gate_eval({"tweet_id": "t1", "user_id": "u1"}, st)
    assert g["proceed"] is True


def test_promoter_state_replied_dedupe_and_kv(tmp_path):
    p = tmp_path / "st.sqlite"
    st = gw.PromoterState(p)
    assert not st.has_replied_to_tweet("99")
    st.mark_replied_tweet("99")
    assert st.has_replied_to_tweet("99")
    st.kv_set("x_search_since_id", "abc")
    assert st.kv_get("x_search_since_id") == "abc"
    st.kv_delete("x_search_since_id")
    assert st.kv_get("x_search_since_id") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
