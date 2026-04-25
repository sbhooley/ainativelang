import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.http_machine_payments import (
    build_payment_challenge_envelope,
    detect_402_wire_profile,
    merge_frame_payment_headers,
    normalize_header_dict,
    resolve_payment_profile,
    summarize_mpp_www_authenticate,
    summarize_x402_payment_required,
)


def test_normalize_header_dict_lowercases_keys():
    h = normalize_header_dict({"Content-Type": "application/json", "X-Test": "1"})
    assert h["content-type"] == "application/json"
    assert h["x-test"] == "1"


def test_detect_402_wire_profile_x402_vs_mpp():
    assert detect_402_wire_profile({"payment-required": "abc"}) == "x402"
    assert detect_402_wire_profile({"www-authenticate": 'Payment id="1", method="tempo"'}) == "mpp"
    assert detect_402_wire_profile({"www-authenticate": 'Basic realm="x"'}) is None


def test_resolve_payment_profile():
    assert resolve_payment_profile("none", {"payment-required": "x"}) is None
    assert resolve_payment_profile("x402", {"payment-required": "x"}) == "x402"
    assert resolve_payment_profile("auto", {"payment-required": "e30="}) == "x402"
    assert resolve_payment_profile("auto", {"www-authenticate": 'Payment id="1"'}) == "mpp"


def test_summarize_x402_payment_required_decodes_json():
    payload = {"amount": "1", "currency": "usd"}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    s = summarize_x402_payment_required(raw)
    assert s["encoding"] == "base64+json"
    assert s["decoded"] == payload


def test_summarize_mpp_www_authenticate_parses_params():
    s = summarize_mpp_www_authenticate('Payment id="abc", method="tempo", realm="mpp.dev"')
    assert s["params"]["id"] == "abc"
    assert s["params"]["method"] == "tempo"
    assert s["params"]["realm"] == "mpp.dev"


def test_merge_frame_payment_headers_combinations():
    base = {"User-Agent": "ainl-tests"}
    ctx = {
        "http_payment": {
            "headers": {"X-Extra": "1"},
            "x402": {"payment_signature": "sig"},
            "mpp": {"authorization_payment": "eyJ"},
        }
    }
    out = merge_frame_payment_headers(base, ctx)
    assert out["User-Agent"] == "ainl-tests"
    assert out["X-Extra"] == "1"
    assert out["PAYMENT-SIGNATURE"] == "sig"
    assert out["Authorization"] == "Payment eyJ"


def test_build_payment_challenge_envelope_includes_url():
    env = build_payment_challenge_envelope(
        profile="x402",
        headers_lc={"payment-required": "e30="},
        headers_orig={},
        body={"detail": "pay"},
        url="https://example.com/r",
    )
    assert env["profile"] == "x402"
    assert env["url"] == "https://example.com/r"
    assert "payment_required" in env
