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


def _core_registry() -> AdapterRegistry:
    r = AdapterRegistry(allowed=["core"])
    r.register("core", CoreBuiltinAdapter())
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


def test_thread_continue_uses_payload_prompt_overrides(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    old_key = os.environ.get("OPENAI_API_KEY")
    old_thread = os.environ.get("PROMOTER_THREAD_ENABLED")
    os.environ["PROMOTER_DRY_RUN"] = "1"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["PROMOTER_THREAD_ENABLED"] = "1"
    try:
        with patch.object(gw, "_openai_chat", return_value="thread custom reply") as mock_chat:
            out = gw.handle_promoter_thread_continue(
                {
                    "payload": {
                        "tweets": [{"id": "t1", "text": "thread text"}],
                        "reply_to_tweet_id": "t1",
                        "conversation_id": "c1",
                        "reply_system_prompt": "Thread system override",
                        "reply_user_prompt": "Thread user override",
                        "reply_fallback_text": "Thread fallback override",
                    }
                },
                st,
            )
            assert out["ok"] is True
            assert out["action"] == "dry_run_thread"
            assert out["text"] == "thread custom reply"
            sent = mock_chat.call_args.args[0]
            assert sent[0]["content"].startswith("Thread system override")
            assert sent[1]["content"] == "Thread user override"
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_thread is None:
            os.environ.pop("PROMOTER_THREAD_ENABLED", None)
        else:
            os.environ["PROMOTER_THREAD_ENABLED"] = old_thread


def test_maybe_daily_retries_on_duplicate_then_posts(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    old_att = os.environ.get("PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS")
    old_key = os.environ.get("OPENAI_API_KEY")
    os.environ["PROMOTER_DRY_RUN"] = "0"
    os.environ["PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS"] = "2"
    os.environ["OPENAI_API_KEY"] = "test-key"
    try:
        dup = {
            "ok": False,
            "error": "post_http_403",
            "detail": {"detail": "You are not allowed to create a Tweet with duplicate content."},
        }
        ok = {"ok": True, "tweet_id": "new123", "raw": {"data": {"id": "new123"}}}
        with patch.object(gw, "_x_post_original", side_effect=[dup, ok]) as mock_post:
            with patch.object(gw, "_openai_chat", return_value="Fresh wording with same link https://github.com/sbhooley/ainativelang"):
                out = gw.handle_maybe_daily({"payload": {"topic": "AINL", "link": "https://github.com/sbhooley/ainativelang"}}, st)
        assert out["ok"] is True
        assert out["action"] == "daily_posted"
        assert out["rewrite_attempts"] == 1
        assert mock_post.call_count == 2
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry
        if old_att is None:
            os.environ.pop("PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS", None)
        else:
            os.environ["PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS"] = old_att
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key


def test_maybe_daily_duplicate_exhaustion_returns_error_message(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    old_dry = os.environ.get("PROMOTER_DRY_RUN")
    old_att = os.environ.get("PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS")
    os.environ["PROMOTER_DRY_RUN"] = "0"
    os.environ["PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS"] = "1"
    try:
        dup = {
            "ok": False,
            "error": "post_http_403",
            "detail": {"detail": "You are not allowed to create a Tweet with duplicate content."},
        }
        with patch.object(gw, "_x_post_original", side_effect=[dup, dup]) as mock_post:
            out = gw.handle_maybe_daily({"payload": {"topic": "AINL", "link": "https://github.com/sbhooley/ainativelang"}}, st)
        assert out["ok"] is False
        assert out["action"] == "daily_failed"
        assert out["attempted_rewrites"] == 1
        assert "duplicate content" in str(out.get("x_error_message", "")).lower()
        assert mock_post.call_count == 2
    finally:
        if old_dry is None:
            os.environ.pop("PROMOTER_DRY_RUN", None)
        else:
            os.environ["PROMOTER_DRY_RUN"] = old_dry
        if old_att is None:
            os.environ.pop("PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS", None)
        else:
            os.environ["PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS"] = old_att


def test_reply_prompt_bundle_default_and_fity_modes():
    mod_path = ROOT / "modules/llm/promoter_reply_prompt_bundle.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )

    old_prof = os.environ.get("PROMOTER_PERSONA_PROFILE")
    try:
        os.environ["PROMOTER_PERSONA_PROFILE"] = "default"
        out_default = eng.run_label(
            "ENTRY",
            frame={"prb_mode": "tweet", "prb_text": "hello world"},
        )
        assert isinstance(out_default, dict)
        assert "Persona profile: fity" not in str(out_default.get("reply_system_prompt", ""))
        assert "Tweet:\nhello world" in str(out_default.get("reply_user_prompt", ""))

        os.environ["PROMOTER_PERSONA_PROFILE"] = "fity"
        out_fity = eng.run_label(
            "ENTRY",
            frame={"prb_mode": "tweet", "prb_text": "hello world"},
        )
        rs = str(out_fity.get("reply_system_prompt", ""))
        assert "Persona profile: fity" in rs
        assert "Never use the word Captain or Captains." in rs
    finally:
        if old_prof is None:
            os.environ.pop("PROMOTER_PERSONA_PROFILE", None)
        else:
            os.environ["PROMOTER_PERSONA_PROFILE"] = old_prof


def test_process_tweet_payload_module_builds_reply_bundle():
    mod_path = ROOT / "modules/llm/promoter_process_tweet_payload.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    out = eng.run_label(
        "ENTRY",
        frame={"ppt_tweet": {"id": "t1", "user_id": "u1", "text": "tweet text"}},
    )
    assert isinstance(out, dict)
    assert isinstance(out.get("payload"), dict)
    assert out["payload"]["id"] == "t1"
    assert "reply_system_prompt" in out
    assert "reply_user_prompt" in out
    assert "reply_fallback_text" in out


def test_thread_continue_payload_module_builds_reply_bundle():
    mod_path = ROOT / "modules/llm/promoter_thread_continue_payload.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    out = eng.run_label(
        "ENTRY",
        frame={
            "ptc_tweets": [{"id": "t1", "text": "thread text"}],
            "ptc_reply_to_tweet_id": "t1",
            "ptc_conversation_id": "c1",
        },
    )
    assert isinstance(out, dict)
    assert out.get("reply_to_tweet_id") == "t1"
    assert out.get("conversation_id") == "c1"
    assert "Thread so far:" in str(out.get("reply_user_prompt", ""))


def test_process_tweet_payload_module_force_static():
    mod_path = ROOT / "modules/llm/promoter_process_tweet_payload.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    out = eng.run_label(
        "ENTRY",
        frame={"ppt_tweet": {"id": "t1", "user_id": "u1", "text": "tweet text"}, "ppt_force_static": 1},
    )
    assert isinstance(out, dict)
    assert out.get("payload", {}).get("id") == "t1"
    assert str(out.get("reply_system_prompt", "")) == ""
    assert str(out.get("reply_user_prompt", "")) == ""
    assert "deterministic" in str(out.get("reply_fallback_text", "")).lower()


def test_error_policy_module_classifies_duplicate_rate_auth_credit():
    mod_path = ROOT / "modules/common/error_policy_from_result.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    dup = eng.run_label(
        "ENTRY",
        frame={"ep_result": {"ok": False, "error": "post_http_403", "detail": {"detail": "You are not allowed to create a Tweet with duplicate content."}}},
    )
    assert dup.get("category") == "duplicate"
    assert dup.get("action") == "rewrite_and_retry"

    rate = eng.run_label(
        "ENTRY",
        frame={"ep_result": {"ok": False, "error": "post_http_429", "detail": {"detail": "Rate limit exceeded"}}},
    )
    assert rate.get("category") == "rate_limit"
    assert rate.get("action") == "retry_later"

    auth = eng.run_label(
        "ENTRY",
        frame={"ep_result": {"ok": False, "error": "post_http_403", "detail": {"detail": "You are not permitted to perform this action."}}},
    )
    assert auth.get("category") == "not_authorized"
    assert auth.get("action") == "skip_target"

    credit = eng.run_label(
        "ENTRY",
        frame={"ep_result": {"ok": False, "error": "llm_http_402", "detail": "This request requires more credits"}},
    )
    assert credit.get("category") == "credit"
    assert credit.get("action") == "fallback_model"


def test_error_policy_apply_module_no_block_path_core_only():
    mod_path = ROOT / "modules/common/error_policy_apply.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    out = eng.run_label(
        "ENTRY",
        frame={"epa_policy": {"action": "none"}, "epa_scope": "promoter_daily"},
    )
    assert out.get("applied") is True
    assert out.get("block_set") is False
    assert out.get("block_key") == "promoter_daily_block_flag"


def test_error_policy_apply_module_sets_kv_for_actions(tmp_path):
    state_path = tmp_path / "st.sqlite"
    mem_path = tmp_path / "mem.sqlite"
    httpd: ThreadingHTTPServer | None = None
    try:
        httpd = _serve_gateway(state_path)
        reg = _registry(httpd.server_port, mem_path)
        mod_path = ROOT / "modules/common/error_policy_apply.ainl"
        code = mod_path.read_text(encoding="utf-8")
        eng = RuntimeEngine.from_code(
            code,
            strict=True,
            adapters=reg,
            source_path=str(mod_path),
        )
        out1 = eng.run_label(
            "ENTRY",
            frame={"epa_policy": {"action": "retry_later"}, "epa_scope": "promoter_daily"},
        )
        assert out1.get("block_set") is True
        assert out1.get("block_key") == "promoter_daily_block_flag"
        assert gw._STATE.kv_get("promoter_daily_block_flag") == "1"

        out2 = eng.run_label(
            "ENTRY",
            frame={"epa_policy": {"action": "fallback_model"}, "epa_scope": "promoter_daily"},
        )
        assert out2.get("block_set") is True
        assert out2.get("block_key") == "promoter_daily_fallback_model_flag"
        raw_fb_ttl = gw._STATE.kv_get("promoter_daily_fallback_model_flag")
        assert raw_fb_ttl is not None
        fb_obj = __import__("json").loads(raw_fb_ttl)
        assert int(fb_obj.get("until_ts", 0)) > 0
        assert fb_obj.get("action") == "fallback_model"

        out3 = eng.run_label(
            "ENTRY",
            frame={
                "epa_policy": {"action": "skip_target"},
                "epa_scope": "promoter_reply",
                "epa_target_id": "u123",
            },
        )
        assert out3.get("block_set") is True
        assert out3.get("block_key") == "promoter_reply_skip_target_u123"
        raw_ttl = gw._STATE.kv_get("promoter_reply_skip_target_u123")
        assert raw_ttl is not None
        sk_obj = __import__("json").loads(raw_ttl)
        assert int(sk_obj.get("until_ts", 0)) > 0
        assert sk_obj.get("action") == "skip_target"
    finally:
        if httpd is not None:
            httpd.shutdown()


def test_skip_target_guard_clears_expired_flag(tmp_path):
    state_path = tmp_path / "st.sqlite"
    mem_path = tmp_path / "mem.sqlite"
    httpd: ThreadingHTTPServer | None = None
    try:
        httpd = _serve_gateway(state_path)
        gw._STATE.kv_set("promoter_reply_skip_target_u9", "1")
        reg = _registry(httpd.server_port, mem_path)
        mod_path = ROOT / "modules/common/error_policy_skip_target_guard.ainl"
        code = mod_path.read_text(encoding="utf-8")
        eng = RuntimeEngine.from_code(
            code,
            strict=True,
            adapters=reg,
            source_path=str(mod_path),
        )
        out = eng.run_label(
            "ENTRY",
            frame={"epsg_scope": "promoter_reply", "epsg_target_id": "u9"},
        )
        assert out.get("should_skip") is False
        assert out.get("reason") in ("expired_cleared", "not_set")
        assert gw._STATE.kv_get("promoter_reply_skip_target_u9") is None
    finally:
        if httpd is not None:
            httpd.shutdown()


def test_skip_target_guard_keeps_active_json_flag(tmp_path):
    state_path = tmp_path / "st.sqlite"
    mem_path = tmp_path / "mem.sqlite"
    httpd: ThreadingHTTPServer | None = None
    try:
        httpd = _serve_gateway(state_path)
        gw._STATE.kv_set("promoter_reply_skip_target_u9", '{"until_ts":9999999999,"action":"skip_target"}')
        reg = _registry(httpd.server_port, mem_path)
        mod_path = ROOT / "modules/common/error_policy_skip_target_guard.ainl"
        code = mod_path.read_text(encoding="utf-8")
        eng = RuntimeEngine.from_code(
            code,
            strict=True,
            adapters=reg,
            source_path=str(mod_path),
        )
        out = eng.run_label(
            "ENTRY",
            frame={"epsg_scope": "promoter_reply", "epsg_target_id": "u9"},
        )
        assert out.get("should_skip") is True
        assert out.get("reason") == "active_ttl"
        assert gw._STATE.kv_get("promoter_reply_skip_target_u9") is not None
    finally:
        if httpd is not None:
            httpd.shutdown()


def test_flag_guard_clears_expired_flag(tmp_path):
    state_path = tmp_path / "st.sqlite"
    mem_path = tmp_path / "mem.sqlite"
    httpd: ThreadingHTTPServer | None = None
    try:
        httpd = _serve_gateway(state_path)
        gw._STATE.kv_set("promoter_daily_fallback_model_flag", "1")
        reg = _registry(httpd.server_port, mem_path)
        mod_path = ROOT / "modules/common/error_policy_flag_guard.ainl"
        code = mod_path.read_text(encoding="utf-8")
        eng = RuntimeEngine.from_code(
            code,
            strict=True,
            adapters=reg,
            source_path=str(mod_path),
        )
        out = eng.run_label("ENTRY", frame={"epfg_key": "promoter_daily_fallback_model_flag"})
        assert out.get("active") is False
        assert out.get("reason") in ("expired_cleared", "not_set")
        assert gw._STATE.kv_get("promoter_daily_fallback_model_flag") is None
    finally:
        if httpd is not None:
            httpd.shutdown()


def test_error_policy_audit_module_shapes_json():
    mod_path = ROOT / "modules/common/error_policy_audit.ainl"
    code = mod_path.read_text(encoding="utf-8")
    eng = RuntimeEngine.from_code(
        code,
        strict=True,
        adapters=_core_registry(),
        source_path=str(mod_path),
    )
    out = eng.run_label(
        "ENTRY",
        frame={
            "epa_result": {"ok": False, "error": "post_http_403"},
            "epa_policy": {"category": "not_authorized", "action": "skip_target"},
            "epa_apply": {"applied": True, "block_set": True},
        },
    )
    parsed = __import__("json").loads(str(out))
    assert parsed.get("result", {}).get("error") == "post_http_403"
    assert parsed.get("policy", {}).get("action") == "skip_target"
    assert parsed.get("apply", {}).get("applied") is True


def test_promoter_stats_bundle_includes_policy_action_buckets(tmp_path):
    st = gw.PromoterState(tmp_path / "st.sqlite")
    gw._STATE = st
    st.audit("process_tweet_policy_skip_target", {"x": 1})
    st.audit("daily_post_rate_limit_cooldown_set", {"x": 1})
    st.audit("process_tweet_fallback_model_active", {"x": 1})
    st.audit("search_cursor_commit", {"since_id": "x"})
    st.kv_set(
        "promoter_daily_fallback_model_flag",
        __import__("json").dumps({"until_ts": 9999999999, "action": "fallback_model"}),
    )
    st.kv_set(
        "promoter_reply_skip_target_u123",
        __import__("json").dumps({"until_ts": 9999999999, "action": "skip_target"}),
    )
    out = gw._promoter_stats_bundle(st)
    assert "policy_actions_last_24h" in out
    p = out["policy_actions_last_24h"]
    assert int(p.get("process_tweet_policy_skip_target", 0)) >= 1
    assert int(p.get("daily_post_rate_limit_cooldown_set", 0)) >= 1
    pn = out.get("policy_actions_normalized_last_24h") or {}
    assert int(pn.get("reply.skip_target", 0)) >= 1
    assert int(pn.get("reply.fallback_active", 0)) >= 1
    ca = out.get("cost_avoidance_last_24h") or {}
    assert int(ca.get("llm_calls_avoided", 0)) >= 2
    assert int(ca.get("x_calls_avoided_est", 0)) >= 1
    cad = out.get("cost_avoidance_daily_7d") or {}
    assert len(cad.get("days") or []) == 7
    assert len(cad.get("llm_calls_avoided") or []) == 7
    assert len(cad.get("x_calls_avoided_est") or []) == 7
    rh = out.get("run_health") or {}
    assert rh.get("last_poll_success_ts") is not None
    assert rh.get("last_poll_success_utc")
    assert int(rh.get("poll_commits_last_hour") or 0) >= 1
    ps = out.get("policy_state") or {}
    assert ps.get("daily_fallback_active") is True
    assert int(ps.get("active_skip_target_count") or 0) >= 1


def test_cost_avoidance_counts_masked_daily_fallback_flag(tmp_path):
    st = gw.PromoterState(tmp_path / "st.sqlite")
    gw._STATE = st
    st.audit("daily_post_deferred_rate_limit", {"x": 1})
    st.audit("search_cursor_commit", {"since_id": "x"})
    st.kv_set(
        "promoter_daily_fallback_model_flag",
        __import__("json").dumps({"until_ts": 9999999999, "action": "fallback_model"}),
    )
    out = gw._promoter_stats_bundle(st)
    ca = out.get("cost_avoidance_last_24h") or {}
    assert int(ca.get("llm_calls_avoided", 0)) >= 1
    cad = out.get("cost_avoidance_daily_7d") or {}
    llm_series = cad.get("llm_calls_avoided") or []
    assert len(llm_series) == 7
    assert int(llm_series[-1]) >= 1


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


def test_promoter_policy_cleanup_clears_stale_flags(tmp_path):
    state_path = tmp_path / "st.sqlite"
    st = gw.PromoterState(state_path)
    gw._STATE = st
    st.kv_set("promoter_daily_block_flag", "1")
    st.kv_set("promoter_daily_fallback_model_flag", '{"until_ts": 1, "action": "fallback_model"}')
    st.kv_set("promoter_reply_fallback_model_flag", '{"until_ts": 9999999999, "action": "fallback_model"}')
    st.kv_set("promoter_reply_skip_target_u1", "1")
    st.kv_set("promoter_reply_skip_target_u2", '{"until_ts": 9999999999, "action": "skip_target"}')
    out = gw.handle_promoter_policy_cleanup({}, st)
    assert out.get("ok") is True
    assert int(out.get("scanned") or 0) >= 5
    assert int(out.get("cleared") or 0) >= 3
    assert st.kv_get("promoter_daily_block_flag") is None
    assert st.kv_get("promoter_daily_fallback_model_flag") is None
    assert st.kv_get("promoter_reply_skip_target_u1") is None
    assert st.kv_get("promoter_reply_fallback_model_flag") is not None
    assert st.kv_get("promoter_reply_skip_target_u2") is not None


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
