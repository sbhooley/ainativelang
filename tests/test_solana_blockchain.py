import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.solana import (
    _PYTH_LEGACY_MAGIC,
    _hermes_api_base,
    _parse_pyth_legacy_price_account,
    _parse_pyth_price_update_v2,
    _resolve_pyth_account_data,
    SolanaAdapter,
)
from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterError
from tooling.effect_analysis import ADAPTER_EFFECT


def test_solana_strict_effect_keys_in_manifest():
    for key in (
        "solana.TRANSFER",
        "solana.TRANSFER_SPL",
        "solana.INVOKE",
        "solana.GET_ACCOUNT",
        "solana.GET_BALANCE",
        "solana.GET_TOKEN_ACCOUNTS",
        "solana.GET_PROGRAM_ACCOUNTS",
        "solana.GET_SIGNATURES_FOR_ADDRESS",
        "solana.GET_LATEST_BLOCKHASH",
        "solana.GET_PYTH_PRICE",
        "solana.HERMES_FALLBACK",
        "solana.GET_MARKET_STATE",
        "solana.DERIVE_PDA",
        "solana.SIMULATE_EVENTS",
    ):
        assert key in ADAPTER_EFFECT


def test_emit_solana_client_contains_registry_and_ir_blob():
    src = 'L1:\n  R core.ADD 1 2 ->x\n  J x\n'
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile(src, emit_graph=True)
    assert not ir.get("errors")
    out = c.emit_solana_client(ir, source_stem="t")
    assert "_IR_B64" in out
    assert "SolanaAdapter" in out
    assert '"solana"' in out or "'solana'" in out
    assert "emit_solana_client" not in out  # method name should not leak into emitted file
    assert "emit_hyperspace_agent" not in out
    assert "demo_preview_embedded_ir" in out
    assert "AINL_SOLANA_DEMO_PREVIEW" in out
    assert "run_ainl(label=" in out
    assert "total step" in out
    assert "GET_LATEST_BLOCKHASH" in out
    assert "Solana adapter verbs" in out
    assert "R solana.GET_LATEST_BLOCKHASH _ ->bh" in out
    assert "Next step (rehearse a tx flow" in out
    assert "SOLANA_VERBS" in out
    assert "from adapters.solana import SOLANA_VERBS" in out
    assert "Future: blockchain.solana.VERB or evm.* may be supported via adapters/blockchain_base.py" in out
    assert "General Blockchain Path" in out
    assert "emit_xxx_client emitter following this pattern (additive only; Hyperspace unchanged)" in out
    assert "print(SOLANA_VERBS)" in out
    assert "Helps debug Solana flows" in out
    assert "Prediction markets (example)" in out
    assert "DERIVE_PDA" in out
    assert "PriceUpdateV2" in out
    assert "HERMES_FALLBACK" in out
    assert "Use DERIVE_PDA for market accounts" in out
    assert "micro-lamports/CU" in out
    assert "GET_PYTH_PRICE" in out
    assert "GET_MARKET_STATE" in out
    assert "prediction_market_demo.ainl" in out
    assert "DISCOVERABILITY" in out
    assert "v1.4.2" in out
    assert "single-quoted" in out
    assert "prediction-market" in out
    assert "solana_quickstart.md" in out


def test_solana_adapter_module_docstring_discoverability():
    import adapters.solana
    doc = adapters.solana.__doc__ or ""
    assert "DISCOVERABILITY" in doc
    assert "v1.4.2" in doc
    assert "single-quoted" in doc
    assert "prediction" in doc.lower()
    assert "solana_quickstart.md" in doc


def test_solana_demo_example_strict_compiles():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "examples", "solana_demo.ainl")
    code = open(path, encoding="utf-8").read()
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors")


def test_prediction_market_demo_strict_compiles():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "examples", "prediction_market_demo.ainl")
    code = open(path, encoding="utf-8").read()
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors")
    assert "Conditional resolution" in code
    assert "Lpayout" in code
    assert "INVOKE" in code and "5000" in code
    assert "DERIVE_PDA" in code
    assert "HERMES_FALLBACK" in code


def test_parse_pyth_legacy_price_account_fields():
    data = bytearray(80)
    struct.pack_into("<I", data, 0, _PYTH_LEGACY_MAGIC)
    struct.pack_into("<i", data, 20, -8)
    struct.pack_into("<Q", data, 40, 123)
    struct.pack_into("<q", data, 48, 100_000_000)
    struct.pack_into("<Q", data, 56, 1_000_000)
    struct.pack_into("<I", data, 64, 1)
    struct.pack_into("<Q", data, 72, 456)
    d = _parse_pyth_legacy_price_account(bytes(data))
    assert d["parser"] == "legacy"
    assert d["price"] == 1.0
    assert d["conf"] == d["confidence"]
    assert d["timestamp"] is None
    assert "timestamp_note" in d
    assert d["status"] == 1
    assert d["publish_slot"] == 456


def test_parse_pyth_legacy_short_data_errors():
    try:
        _parse_pyth_legacy_price_account(b"\x00" * 10)
        assert False, "expected ValueError for short account data"
    except ValueError as e:
        msg = str(e).lower()
        assert "80" in msg and "at least" in msg


def test_parse_pyth_price_update_v2_sample():
    try:
        import solders  # noqa: F401
    except ImportError:
        return
    import base64

    b64 = "IvEjY51+9M1gMUcENA3t3zcf1CRyFI8kjp0abRpesqw6zYt/1dayQwHvDYtv2izrpB2hXUCV0do5Kg0vjtDGx7wPTPrIwoC1bbJMyugBAAAAQF5VAAAAAAD4////9SnJaQAAAAD1KclpAAAAABTNI+oBAAAAAylTAAAAAAD15WoYAAAAAAA="
    data = base64.b64decode(b64)
    d = _parse_pyth_price_update_v2(data)
    assert d["parser"] == "v2"
    assert d["verification_level"]["kind"] == "full"
    assert d["exponent"] == -8
    assert d["timestamp"] is not None
    assert "write_authority" in d


def test_derive_pda_and_hermes_dry_run():
    old_hermes = os.environ.pop("AINL_PYTH_HERMES_URL", None)
    os.environ["AINL_DRY_RUN"] = "1"
    try:
        assert _hermes_api_base() == "https://hermes.pyth.network"
        os.environ["AINL_PYTH_HERMES_URL"] = "https://custom.hermes.test"
        assert _hermes_api_base() == "https://custom.hermes.test"
        a = SolanaAdapter()
        pda = a.call("DERIVE_PDA", ['["market","x"]', "11111111111111111111111111111111"], {})
        assert pda.get("ok") is True
        assert pda.get("dry_run") is True
        assert pda.get("address", "").startswith("DRYRUN_PDA_")
        assert pda.get("bump") == 254
        h = a.call(
            "HERMES_FALLBACK",
            ["ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d"],
            {},
        )
        assert h.get("parser") == "hermes"
        assert h.get("dry_run") is True
        assert h.get("price") == 123.45
        assert h.get("hermes_base") == "https://custom.hermes.test"
    finally:
        os.environ.pop("AINL_DRY_RUN", None)
        os.environ.pop("AINL_PYTH_HERMES_URL", None)
        if old_hermes is not None:
            os.environ["AINL_PYTH_HERMES_URL"] = old_hermes


def test_resolve_pyth_error_suggests_hermes_fallback():
    try:
        _resolve_pyth_account_data(b"\x00" * 8, "11111111111111111111111111111111", False)
        assert False, "expected AdapterError"
    except AdapterError as e:
        msg = str(e)
        assert "HERMES_FALLBACK" in msg
        assert "feed_id_hex" in msg.lower()
        assert "hermes.pyth.network" in msg
