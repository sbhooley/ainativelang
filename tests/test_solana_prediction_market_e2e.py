"""
E2E: strict compile → RuntimeEngine → real SolanaAdapter dispatch (dry-run, no network).
"""
import asyncio
import os
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.solana import SolanaAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine


@contextmanager
def _ainl_dry_run():
    prev = os.environ.get("AINL_DRY_RUN")
    os.environ["AINL_DRY_RUN"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("AINL_DRY_RUN", None)
        else:
            os.environ["AINL_DRY_RUN"] = prev


def _registry_with_solana() -> AdapterRegistry:
    reg = AdapterRegistry(allowed=["core", "solana"])
    reg.register("solana", SolanaAdapter())
    return reg


# Single-quoted JSON (recommended): inner " are literal; one lexer token.
_MULTISTEP_DERIVE_PDA_STRINGIFY = (
    "L1:\n"
    "  R solana.DERIVE_PDA '[\"m\",\"1\"]' \"11111111111111111111111111111111\" ->pda\n"
    "  R core.STRINGIFY pda ->out\n"
    "  J out\n"
)

_MULTISTEP_BLOCKHASH_STRINGIFY = (
    "L1:\n"
    "  R solana.GET_LATEST_BLOCKHASH _ ->bh\n"
    "  R core.STRINGIFY bh ->out\n"
    "  J out\n"
)


def test_solana_compile_runtime_engine_hermes_fallback_dry_run_e2e():
    """Compile a minimal solana graph, run through RuntimeEngine with SolanaAdapter under AINL_DRY_RUN."""
    with _ainl_dry_run():
        feed = "ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d"
        code = (
            f"L1:\n"
            f'  R solana.HERMES_FALLBACK "{feed}" ->hq\n'
            f"  J hq\n"
        )
        eng = RuntimeEngine.from_code(code, strict=True, adapters=_registry_with_solana())
        out = eng.run_label("1", frame={})
        assert isinstance(out, dict)
        assert out.get("dry_run") is True
        assert out.get("parser") == "hermes"
        assert out.get("source") == "hermes"
        assert out.get("ok") is True
        assert out.get("feed_id_hex") == feed
        assert "hermes_base" in out


def test_solana_derive_pda_stringify_multistep_dry_run_e2e():
    """Two R steps: DERIVE_PDA → core.STRINGIFY (frame wiring) under dry-run."""
    with _ainl_dry_run():
        eng = RuntimeEngine.from_code(
            _MULTISTEP_DERIVE_PDA_STRINGIFY,
            strict=True,
            adapters=_registry_with_solana(),
        )
        out = eng.run_label("1", frame={})
    assert isinstance(out, str)
    assert "DRYRUN_PDA_" in out
    assert '"dry_run": true' in out
    assert '"seeds_count": 2' in out


def test_solana_derive_pda_stringify_multistep_async_dry_run_e2e():
    """Same graph as sync test; runtime_async uses SolanaAdapter.call_async for R steps."""
    with _ainl_dry_run():
        eng = RuntimeEngine.from_code(
            _MULTISTEP_DERIVE_PDA_STRINGIFY,
            strict=True,
            adapters=_registry_with_solana(),
            runtime_async=True,
        )
        out = asyncio.run(eng.run_label_async("1", frame={}))
    assert isinstance(out, str)
    assert "DRYRUN_PDA_" in out
    assert '"dry_run": true' in out


def test_solana_blockhash_stringify_multistep_dry_run_e2e():
    """GET_LATEST_BLOCKHASH → STRINGIFY (same shape as prediction_market_demo read path)."""
    with _ainl_dry_run():
        eng = RuntimeEngine.from_code(
            _MULTISTEP_BLOCKHASH_STRINGIFY,
            strict=True,
            adapters=_registry_with_solana(),
        )
        out = eng.run_label("1", frame={})
    assert isinstance(out, str)
    assert "DRYRUN_BH_" in out
    assert '"dry_run": true' in out


def test_solana_invoke_mutation_envelope_dry_run_e2e():
    """Mutating verb under AINL_DRY_RUN: INVOKE returns simulated envelope (no solders/RPC required)."""
    with _ainl_dry_run():
        code = (
            "L1:\n"
            '  R solana.INVOKE "11111111111111111111111111111111" "AA==" "[]" 5000 ->inv\n'
            "  J inv\n"
        )
        eng = RuntimeEngine.from_code(code, strict=True, adapters=_registry_with_solana())
        out = eng.run_label("1", frame={})
    assert isinstance(out, dict)
    assert out.get("ok") is True
    assert out.get("dry_run") is True
    assert out.get("simulated") is True
    assert out.get("verb") == "INVOKE"
    assert out.get("program_id") == "11111111111111111111111111111111"
    assert out.get("instruction_len") == 1  # base64 "AA==" -> one byte
    assert out.get("accounts") == []
    assert out.get("priority_fee_microlamports") == 5000
    sig = str(out.get("signature") or "")
    assert sig.startswith("DRYRUN_INVOKE_")


def test_solana_transfer_mutation_envelope_dry_run_e2e():
    """Mutating TRANSFER under AINL_DRY_RUN returns simulated envelope (no solders/RPC)."""
    with _ainl_dry_run():
        code = (
            "L1:\n"
            '  R solana.TRANSFER "11111111111111111111111111111111" 1000 ->sig\n'
            "  J sig\n"
        )
        eng = RuntimeEngine.from_code(code, strict=True, adapters=_registry_with_solana())
        out = eng.run_label("1", frame={})
    assert isinstance(out, dict)
    assert out.get("ok") is True
    assert out.get("dry_run") is True
    assert out.get("verb") == "TRANSFER"
    assert out.get("to") == "11111111111111111111111111111111"
    assert out.get("lamports") == 1000
    assert out.get("fee_lamports_estimate") == 5000
    assert str(out.get("signature") or "").startswith("DRYRUN_TRANSFER_")


def test_solana_transfer_spl_mutation_envelope_dry_run_e2e():
    """Mutating TRANSFER_SPL under AINL_DRY_RUN returns simulated envelope (no solders/RPC)."""
    with _ainl_dry_run():
        code = (
            "L1:\n"
            '  R solana.TRANSFER_SPL "11111111111111111111111111111111" '
            '"11111111111111111111111111111111" "11111111111111111111111111111111" '
            '"11111111111111111111111111111111" 42 9 ->sig\n'
            "  J sig\n"
        )
        eng = RuntimeEngine.from_code(code, strict=True, adapters=_registry_with_solana())
        out = eng.run_label("1", frame={})
    assert isinstance(out, dict)
    assert out.get("ok") is True
    assert out.get("dry_run") is True
    assert out.get("verb") == "TRANSFER_SPL"
    assert out.get("mint") == "11111111111111111111111111111111"
    assert out.get("amount") == 42
    assert out.get("decimals") == 9
    assert str(out.get("signature") or "").startswith("DRYRUN_TRANSFER_SPL_")
