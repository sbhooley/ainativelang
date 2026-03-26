"""Integration: apollo-x-bot gateway + ainl-x-promoter.ainl with ExecutorBridgeAdapter."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apollo-x-bot"))
import gateway_server as gw  # noqa: E402

from runtime.adapters.builtins import CoreBuiltinAdapter  # noqa: E402
from runtime.adapters.executor_bridge import ExecutorBridgeAdapter  # noqa: E402
from runtime.adapters.memory import MemoryAdapter  # noqa: E402
from runtime.adapters.base import AdapterRegistry  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402


def _serve_gateway(state_path: Path) -> ThreadingHTTPServer:
    gw._STATE = gw.PromoterState(state_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), gw.GatewayHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _registry(port: int, memory_db: Path) -> AdapterRegistry:
    base = f"http://127.0.0.1:{port}"
    endpoints = {
        "x.search": f"{base}/v1/x.search",
        "llm.classify": f"{base}/v1/llm.classify",
        "llm.chat": f"{base}/v1/llm.chat",
        "llm.json_array_extract": f"{base}/v1/llm.json_array_extract",
        "llm.merge_classify_rows": f"{base}/v1/llm.merge_classify_rows",
        "promoter.text_contains_any": f"{base}/v1/promoter.text_contains_any",
        "promoter.heuristic_scores": f"{base}/v1/promoter.heuristic_scores",
        "promoter.classify_prompts": f"{base}/v1/promoter.classify_prompts",
        "promoter.daily_post_prompts": f"{base}/v1/promoter.daily_post_prompts",
        "promoter.daily_snippets": f"{base}/v1/promoter.daily_snippets",
        "promoter.gate_eval": f"{base}/v1/promoter.gate_eval",
        "promoter.process_tweet": f"{base}/v1/promoter.process_tweet",
        "promoter.discover_tweet_authors": f"{base}/v1/promoter.discover_tweet_authors",
        "promoter.discovery_candidates_from_tweets": f"{base}/v1/promoter.discovery_candidates_from_tweets",
        "promoter.discovery_score_users": f"{base}/v1/promoter.discovery_score_users",
        "promoter.discovery_apply_one": f"{base}/v1/promoter.discovery_apply_one",
        "promoter.discovery_apply_batch": f"{base}/v1/promoter.discovery_apply_batch",
        "promoter.search_cursor_commit": f"{base}/v1/promoter.search_cursor_commit",
        "promoter.maybe_daily_post": f"{base}/v1/promoter.maybe_daily_post",
        "kv.get": f"{base}/v1/kv.get",
        "kv.set": f"{base}/v1/kv.set",
    }
    r = AdapterRegistry(allowed=["core", "bridge", "memory"])
    r.register("core", CoreBuiltinAdapter())
    r.register("bridge", ExecutorBridgeAdapter(endpoints=endpoints, default_timeout_s=120.0))
    r.register("memory", MemoryAdapter(db_path=str(memory_db)))
    return r


def test_promoter_graph_runs_with_gateway_dry_run():
    fd, tmp = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.unlink(tmp)
    state_path = Path(tmp)
    fd_m, tmp_m = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd_m)
    os.unlink(tmp_m)
    memory_path = Path(tmp_m)

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
            adapters=_registry(port, memory_path),
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
        if memory_path.exists():
            memory_path.unlink()
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


def test_gateway_llm_classify_raw_without_messages_falls_back_not_envelope_error(tmp_path):
    """classify_response=raw without messages must not trigger envelope_missing_messages (legacy path)."""
    state_path = tmp_path / "st.sqlite"
    gw._STATE = gw.PromoterState(state_path)
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    try:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        out = gw.handle_llm_classify(
            {
                "classify_response": "raw",
                "tweets": [{"id": "z", "text": "OpenClaw orchestration"}],
            },
            gw._STATE,
        )
        assert isinstance(out, list)
        assert out[0]["id"] == "z"
        assert float(out[0]["score"]) >= 1.0
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry


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


def test_apply_persona_instructions_respects_fity_profile(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_prof = os.environ.get("PROMOTER_PERSONA_PROFILE")
    os.environ["PROMOTER_PERSONA_PROFILE"] = "fity"
    try:
        s = gw._apply_persona_instructions("Base prompt", "reply")
        assert "Persona profile: fity" in s
        assert "Never use the word Captain or Captains." in s
    finally:
        if old_prof is None:
            os.environ.pop("PROMOTER_PERSONA_PROFILE", None)
        else:
            os.environ["PROMOTER_PERSONA_PROFILE"] = old_prof


def test_process_tweet_missing_tweet_id_skips_without_x_post(tmp_path):
    """Empty/missing tweet id must not call X post (avoids in_reply_to_tweet_id='' 400)."""
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    os.environ["PROMOTER_DRY_RUN"] = "0"
    try:
        with patch.object(gw, "_x_post_reply") as mock_x_post:
            out = gw.handle_process_tweet(
                {"payload": {"text": "hello", "user_id": "u1"}},
                st,
            )
            assert out["ok"] is True
            assert out.get("reason") == "missing_tweet_id"
            assert out.get("action") == "skipped"
            mock_x_post.assert_not_called()

        with patch.object(gw, "_x_post_reply") as mock_x_post:
            out2 = gw.handle_process_tweet(
                {"payload": {"id": "", "text": "hello", "user_id": "u1"}},
                st,
            )
            assert out2.get("reason") == "missing_tweet_id"
            mock_x_post.assert_not_called()
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry


def test_gate_eval_missing_tweet_id_does_not_proceed(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    g = gw.handle_promoter_gate_eval({"tweet_id": "", "user_id": "u1"}, st)
    assert g["proceed"] is False
    assert g.get("reason") == "missing_tweet_id"


def test_process_tweet_uses_payload_prompt_overrides(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    old_key = os.environ.get("OPENAI_API_KEY")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    os.environ["OPENAI_API_KEY"] = "test-key"
    try:
        with patch.object(gw, "_openai_chat", return_value="custom reply") as mock_chat:
            out = gw.handle_process_tweet(
                {
                    "payload": {
                        "id": "t1",
                        "user_id": "u1",
                        "text": "tweet text",
                        "reply_system_prompt": "System override",
                        "reply_user_prompt": "User override",
                        "reply_fallback_text": "Fallback override",
                    }
                },
                st,
            )
            assert out["ok"] is True
            assert out["action"] == "dry_run_reply"
            assert out["text"] == "custom reply"
            sent = mock_chat.call_args.args[0]
            assert sent[0]["content"].startswith("System override")
            assert sent[1]["content"] == "User override"
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key


def test_gateway_discovery_track_a_preflight_skips_when_dry_run(tmp_path):
    """Track A endpoints return empty + skipped when PROMOTER_DRY_RUN=1 (same as monolithic preflight)."""
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    try:
        tweets = [{"id": "1", "user_id": "u1", "text": "hi"}]
        c = gw.handle_promoter_discovery_candidates_from_tweets({"tweets": tweets}, st)
        assert c.get("skipped") is True
        assert c.get("users") == []
        s = gw.handle_promoter_discovery_score_users({"users": [{"user_id": "u1", "username": "a"}]}, st)
        assert s.get("skipped") is True
        assert s.get("items") == []
        b = gw.handle_promoter_discovery_apply_batch({"items": [{"user_id": "u1", "username": "a", "score": 9.0}]}, st)
        assert b.get("skipped") is True
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry


def test_gateway_kv_get_set(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    assert gw.handle_kv_get({}, st) == {"ok": False, "error": "missing_key"}
    assert gw.handle_kv_set({"key": "k1", "value": "v1"}, st) == {"ok": True}
    assert gw.handle_kv_get({"key": "k1"}, st) == {"ok": True, "value": "v1"}
    assert gw.handle_kv_set({"key": "k1", "value": None}, st) == {"ok": True}
    assert gw.handle_kv_get({"key": "k1"}, st) == {"ok": True, "value": None}


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
