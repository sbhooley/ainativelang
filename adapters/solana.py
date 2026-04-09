"""
Solana RPC adapter — first concrete member of the **blockchain.solana** family in policy/docs.

DISCOVERABILITY / QUICK START (AINL v1.4.6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

AINL provides native Solana support for deterministic AI agent workflows in prediction markets, Pyth oracles, PDA
derivation, and low-cost on-chain actions. Use this adapter when you want a strict, explainable graph that reads market
state, resolves using on-chain or Hermes/Pyth prices, and rehearses or executes settlement flows with priority fees.

- **DERIVE_PDA** — derive market PDAs / vaults from **single-quoted JSON** seeds, e.g. ``R solana.DERIVE_PDA
  '[\"market\",\"MY_MARKET_ID\"]' \"YourProgram1111111111111111111111111111111111\" ->pda``. Single quotes keep the JSON
  array as **one** token for the strict lexer; inner double quotes are literal.
- **GET_PYTH_PRICE + HERMES_FALLBACK** — on-chain Pyth price (legacy PriceAccount + PriceUpdateV2) plus off-chain Hermes
  fallback for robust resolution monitoring; both are safe to use under ``AINL_DRY_RUN=1`` for deterministic tests.
- **INVOKE / TRANSFER_SPL (priority fees)** — rehearse and execute cost-controlled trades/payouts using a trailing
  **micro-lamports per compute unit** argument (e.g. ``R solana.INVOKE ... 5000 ->out``) for congested-slot routing and
  settlement; under ``AINL_DRY_RUN=1`` these verbs emit structured **simulation envelopes** instead of sending txs.

Strings and JSON args: prefer **single-quoted** strings when passing JSON (e.g. seeds or account lists) so inner
double quotes are preserved without extra escaping; double quotes remain supported when you need explicit escape
sequences. Start with ``examples/prediction_market_demo.ainl`` and ``docs/solana_quickstart.md`` for end-to-end flows;
the ``--emit solana-client`` emitter produces standalone clients with embedded IR and runnable Solana demos.

This is the first concrete implementation of the **BlockchainAdapterBase** family. Future adapters
(e.g., ``evm``) can follow the same verb + dry-run + ``_`` placeholder pattern.

Strict-mode DSL uses the single-segment namespace **``solana``** (``R solana.VERB ...``) because
``adapter.verb`` strict keys only split on the **first** dot. A dotted ``blockchain.solana.*`` form
is reserved for future registry taxonomy; runtime registration remains ``\"solana\"``.

Packages (lazy-loaded): ``solana``, ``solders``; SPL helpers may import ``spl.token``.

Environment:
  AINL_SOLANA_RPC_URL — JSON-RPC URL (default: https://api.devnet.solana.com)
  AINL_SOLANA_KEYPAIR_JSON — JSON array of 64 bytes OR path to keypair JSON file
  AINL_DRY_RUN — when truthy, mutating verbs return simulated envelopes without sending
  AINL_PYTH_HERMES_URL — optional origin for **HERMES_FALLBACK** (default: https://hermes.pyth.network; path ``/v2/updates/price/latest`` is appended)
  AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT — max token accounts to return after fetch (default: 500; cap 10000)
  AINL_SOLANA_GET_PROGRAM_ACCOUNTS_LIMIT — max program accounts to return (default: 100; cap 10000)

Optional **frame / context** overrides (never logged):
  _solana_keypair_json — same shape as AINL_SOLANA_KEYPAIR_JSON (path or JSON bytes)
  _ainl_solana_keypair_json — alias for the above

Strict / dotted verbs (examples):
  R solana.GET_ACCOUNT pubkey ->info
      ``pubkey`` fills the required target slot (use a real address, not ``_``).
  R solana.GET_BALANCE pubkey ->lamports
  R solana.GET_TOKEN_ACCOUNTS owner_pubkey [mint_pubkey] [limit] ->accounts
      Without mint, RPC uses SPL Token program filter — responses can be huge; results are capped
      by AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT and optional third-arg ``limit``. Prefer passing ``mint``.
  R solana.GET_PROGRAM_ACCOUNTS program_id [filters_json] [limit] ->rows
      ``filters_json`` is a JSON array: dataSize ints and/or {{"offset": n, "bytes": "base58..."}} memcmp.
      Second arg may be a numeric limit if you omit filters: program_id then limit only.
  R solana.GET_SIGNATURES_FOR_ADDRESS address [limit] ->sigs
  R solana.GET_LATEST_BLOCKHASH _ ->bh
      ``_`` is an ignored placeholder (parser requires a target token). Live: getLatestBlockhash; AINL_DRY_RUN=1 returns mock.
  R solana.TRANSFER dest_pubkey lamports ->sig
  R solana.TRANSFER_SPL mint source dest owner amount [decimals] ->sig
  R solana.INVOKE program_id data_b64 [accounts_json] [priority_fee_microlamports] ->out
      Optional trailing int: **SetComputeUnitPrice** in **micro-lamports per compute unit** (not whole lamports) —
      typical priority-fee knob for congested slots; prediction markets / settlement / DFlow-composed routes.
  R solana.GET_PYTH_PRICE price_feed_pubkey [expect_update_account] ->px
      On-chain price: **legacy** PriceAccount (magic ``0xA1B2C3D4``) or **PriceUpdateV2** (~134 B, push/receiver feeds).
      Optional second arg ``true`` / ``1`` prefers the V2 path when layout is ambiguous. Unified ``parser`` field:
      ``\"legacy\"`` | ``\"v2\"``. For off-chain quotes use **HERMES_FALLBACK** or ``http`` adapters.
  R solana.HERMES_FALLBACK feed_id_hex ->hq
      Off-chain **Hermes** latest price (``/v2/updates/price/latest``). ``feed_id_hex`` is 64 hex chars (same id as Pyth
      price-feed list). Use when RPC/V2 is flaky or for cross-checks; pairs with **GET_PYTH_PRICE** for hybrid resolution.
  R solana.DERIVE_PDA seeds_json program_id ->pda
      ``seeds_json`` is a JSON array of UTF-8 string seeds. Prefer **single-quoted** JSON, e.g.
      ``'["market","MY_MARKET_ID"]'`` (one lexer token; inner double quotes are literal). Alternatively use one
      double-quoted string with escaped inner quotes. Returns ``address``, ``bump``, ``program_id`` — for prediction-market
      PDAs and program-derived vaults (live derivation needs **solders**).
  R solana.GET_MARKET_STATE market_pubkey ->mst
      Same payload as GET_ACCOUNT with ``read_as: \"market_state\"`` — convenience for market PDAs (prediction pools).
  R solana.SIMULATE_EVENTS [program_id] ->events
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import struct
import urllib.error
import urllib.request
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple

from adapters.blockchain_base import BlockchainAdapterBase
from runtime.adapters.base import AdapterError

_KEYPAIR_HINT = (
    "Create a keypair safely: `solana-keygen new -o ./key.json` (keep the file secret; never commit it). "
    "Then `export AINL_SOLANA_KEYPAIR_JSON=./key.json` or set frame `_solana_keypair_json` to that path. "
    "For simulation without signing, use `AINL_DRY_RUN=1`."
)

# Supported strict verbs (R solana.<VERB>); keep aligned with emit_solana_client demo_preview and docs.
# Aligned with BlockchainAdapterBase for future evm./other chain adapters sharing the same verb-list pattern.
SOLANA_VERBS: Tuple[str, ...] = (
    "GET_ACCOUNT",
    "GET_BALANCE",
    "GET_TOKEN_ACCOUNTS",
    "GET_PROGRAM_ACCOUNTS",
    "GET_SIGNATURES_FOR_ADDRESS",
    "GET_LATEST_BLOCKHASH",
    "GET_PYTH_PRICE",
    "HERMES_FALLBACK",
    "GET_MARKET_STATE",
    "DERIVE_PDA",
    "TRANSFER",
    "TRANSFER_SPL",
    "INVOKE",
    "SIMULATE_EVENTS",
)


def _truthy_env(name: str) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _rpc_url() -> str:
    return (os.environ.get("AINL_SOLANA_RPC_URL") or "").strip() or "https://api.devnet.solana.com"


def _hermes_api_base() -> str:
    """Hermes REST API origin for ``HERMES_FALLBACK``; override with ``AINL_PYTH_HERMES_URL``, else ``https://hermes.pyth.network``."""
    return (os.environ.get("AINL_PYTH_HERMES_URL") or "").strip() or "https://hermes.pyth.network"


def _is_dry_run() -> bool:
    return _truthy_env("AINL_DRY_RUN") or _truthy_env("DRY_RUN")


def _dry_run_signature(verb: str) -> str:
    """Deterministic-looking mock signature (not a real chain transaction)."""
    tail = secrets.token_hex(16)
    return f"DRYRUN_{verb}_{tail}"


def _mock_latest_blockhash() -> str:
    """Placeholder blockhash when AINL_DRY_RUN avoids getLatestBlockhash RPC."""
    return "DRYRUN_BH_" + secrets.token_hex(32)


def _dry_run_mutation_envelope(verb: str, **extra: Any) -> Dict[str, Any]:
    """Consistent mock shape for all mutating verbs under dry-run."""
    out: Dict[str, Any] = {
        "ok": True,
        "dry_run": True,
        "simulated": True,
        "verb": verb,
        "signature": _dry_run_signature(verb),
        "note": "No transaction sent (AINL_DRY_RUN or DRY_RUN enabled).",
    }
    out.update(extra)
    return out


def _ctx_keypair_raw(context: Optional[Dict[str, Any]]) -> str:
    if not isinstance(context, dict):
        return ""
    for k in ("_solana_keypair_json", "_ainl_solana_keypair_json"):
        v = context.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _load_keypair_bytes_from_json(data: Any):
    try:
        from solders.keypair import Keypair as SoldersKeypair
    except ImportError as e:
        raise AdapterError(
            "solders is required for Solana signing; install: pip install 'ainativelang[solana]'"
        ) from e
    if isinstance(data, list) and len(data) >= 32:
        return SoldersKeypair.from_bytes(bytes(data[:64] if len(data) >= 64 else data))
    raise AdapterError(
        "keypair JSON must be a byte array with at least 32 entries (64 bytes typical). "
        + _KEYPAIR_HINT
    )


def _resolve_keypair(context: Optional[Dict[str, Any]] = None):
    """Load keypair from context override first, then AINL_SOLANA_KEYPAIR_JSON."""
    raw = _ctx_keypair_raw(context) or (os.environ.get("AINL_SOLANA_KEYPAIR_JSON") or "").strip()
    if not raw:
        return None
    try:
        path = os.path.expanduser(raw)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AdapterError(
            f"Keypair config: expected a path to JSON from solana-keygen or an inline JSON byte array ({e}). "
            + _KEYPAIR_HINT
        ) from e
    except OSError as e:
        raise AdapterError(f"Keypair config: cannot read path {raw!r}: {e}. " + _KEYPAIR_HINT) from e
    return _load_keypair_bytes_from_json(data)


def _rpc_failure_message(exc: BaseException, *, where: str) -> str:
    detail = (str(exc) or "").strip() or repr(exc)
    return (
        f"Solana RPC error ({where}): {detail}. "
        "Check AINL_SOLANA_RPC_URL (default devnet), connectivity, and rate limits; retry later or use another endpoint. "
        "For a local signing keypair: `solana-keygen new -o ./key.json` (keep private; never commit)."
    )


def _is_int_like(a: Any) -> bool:
    if isinstance(a, bool):
        return False
    if isinstance(a, int):
        return True
    if isinstance(a, float):
        return a == int(a)
    s = str(a).strip()
    return s.isdigit() or (s.startswith("-") and s[1:].isdigit())


def _parse_filters_json(raw: Any) -> Optional[List[Any]]:
    """Build solana-py filter list: ints (dataSize) and MemcmpOpts."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise AdapterError(f"solana.GET_PROGRAM_ACCOUNTS filters must be valid JSON array: {e}") from e
    if not isinstance(data, list):
        raise AdapterError("filters JSON must be an array of dataSize ints and/or memcmp objects")
    from solana.rpc.types import MemcmpOpts

    out: List[Any] = []
    for x in data:
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, dict):
            off = x.get("offset")
            b = x.get("bytes")
            if off is None or b is None:
                raise AdapterError("memcmp filter objects need 'offset' and 'bytes'")
            out.append(MemcmpOpts(offset=int(off), bytes=str(b)))
        else:
            raise AdapterError("filter entries must be int (dataSize) or object (memcmp)")
    return out


def _parse_program_accounts_args(
    args: List[Any],
) -> Tuple[Any, Optional[List[Any]], int]:
    if not args:
        raise AdapterError("solana.GET_PROGRAM_ACCOUNTS requires program_id [filters_json] [limit]")
    try:
        from solders.pubkey import Pubkey

        prog = Pubkey.from_string(str(args[0]))
    except Exception as e:
        raise AdapterError(f"invalid program id: {e}") from e

    default_lim = int(os.environ.get("AINL_SOLANA_GET_PROGRAM_ACCOUNTS_LIMIT") or "100")
    default_lim = max(1, min(default_lim, 10000))
    filters: Optional[List[Any]] = None
    limit = default_lim

    if len(args) == 2:
        if _is_int_like(args[1]):
            limit = max(1, min(int(args[1]), 10000))
        else:
            filters = _parse_filters_json(args[1])
    elif len(args) >= 3:
        filters = _parse_filters_json(args[1])
        limit = max(1, min(int(args[2]), 10000))
    return prog, filters, limit


# Pyth on-chain legacy PriceAccount (pyth-sdk layout): magic at 0, exponent at 20, agg price at 48.
_PYTH_LEGACY_MAGIC = 0xA1B2C3D4
_PYTH_LEGACY_MIN_LEN = 80


def _parse_pyth_legacy_price_account(data: bytes) -> Dict[str, Any]:
    """Best-effort parse of Pyth **PriceAccount** account data (classic on-chain price feeds)."""
    if len(data) < _PYTH_LEGACY_MIN_LEN:
        raise ValueError(
            f"Pyth legacy PriceAccount requires at least {_PYTH_LEGACY_MIN_LEN} bytes, got {len(data)}; "
            "check account owner/program or use pull/Hermes feeds (not parsed here)"
        )
    magic = struct.unpack_from("<I", data, 0)[0]
    exp = struct.unpack_from("<i", data, 20)[0]
    price_i64 = struct.unpack_from("<q", data, 48)[0]
    conf_u64 = struct.unpack_from("<Q", data, 56)[0]
    status_u32 = struct.unpack_from("<I", data, 64)[0]
    valid_slot = struct.unpack_from("<Q", data, 40)[0]
    pub_slot = struct.unpack_from("<Q", data, 72)[0]
    scale = float(10**exp)
    price_human = float(price_i64) * scale
    conf_human = float(conf_u64) * scale
    out: Dict[str, Any] = {
        "parser": "legacy",
        "magic": magic,
        "magic_expected": _PYTH_LEGACY_MAGIC,
        "exponent": exp,
        "price": price_human,
        "conf": conf_human,
        "confidence": conf_human,
        "price_raw": price_i64,
        "conf_raw": conf_u64,
        "status": status_u32,
        "valid_slot": int(valid_slot),
        "publish_slot": int(pub_slot),
        # Wall-clock unix time is not stored in legacy layout; callers use slots for freshness ordering.
        "timestamp": None,
        "timestamp_note": "legacy PriceAccount has no unix timestamp; use publish_slot / valid_slot vs cluster",
    }
    if magic != _PYTH_LEGACY_MAGIC:
        out["layout_warning"] = "magic mismatch — verify this pubkey is a legacy Pyth price feed"
    return out


def _truthy_arg(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "on")


def _pyth_price_update_account_note() -> Dict[str, Any]:
    """Placeholder when user points at a price *update* (post-pull) account — layout differs from legacy PriceAccount."""
    return {
        "pyth_update_account": True,
        "note": (
            "Price-update accounts (pull oracle / post-aggregation) use a different layout than legacy PriceAccount. "
            "Use a legacy on-chain feed pubkey for GET_PYTH_PRICE, or consume Hermes/API off-chain for pull feeds."
        ),
    }


# Pyth Solana Receiver — Anchor `PriceUpdateV2` (borsh); `posted_slot` follows `PriceFeedMessage`.
_PYTH_V2_MIN_LEN = 134


def _parse_pyth_price_update_v2(data: bytes) -> Dict[str, Any]:
    """Best-effort parse of Pyth **PriceUpdateV2** on-chain account (receiver program, push-style feeds)."""
    if len(data) < _PYTH_V2_MIN_LEN:
        raise ValueError(
            f"PriceUpdateV2 expects at least {_PYTH_V2_MIN_LEN} bytes, got {len(data)}; "
            "not a Pyth receiver price-update account or truncated RPC data"
        )
    try:
        from solders.pubkey import Pubkey
    except ImportError as e:
        raise ValueError("solders required to decode Pyth V2 accounts; pip install 'ainativelang[solana]'") from e
    try:
        wpk = Pubkey.from_bytes(bytes(data[8:40]))
    except AttributeError:
        wpk = Pubkey(bytes(data[8:40]))
    write_authority = str(wpk)
    off = 40
    tag = data[off]
    off += 1
    if tag == 0:
        if off >= len(data):
            raise ValueError("PriceUpdateV2 Partial variant truncated")
        num_sig = int(data[off])
        off += 1
        verification_level: Dict[str, Any] = {"kind": "partial", "num_signatures": num_sig}
    elif tag == 1:
        verification_level = {"kind": "full"}
    else:
        verification_level = {"kind": "unknown", "discriminator": tag}
    need = off + 84 + 8
    if len(data) < need:
        raise ValueError(
            f"PriceUpdateV2 message/posted_slot truncated (need {need} bytes at offset {off}, have {len(data)})"
        )
    feed_id = bytes(data[off : off + 32])
    off += 32
    price_i64 = struct.unpack_from("<q", data, off)[0]
    off += 8
    conf_u64 = struct.unpack_from("<Q", data, off)[0]
    off += 8
    exp_i32 = struct.unpack_from("<i", data, off)[0]
    off += 4
    publish_time = struct.unpack_from("<q", data, off)[0]
    off += 8
    prev_publish_time = struct.unpack_from("<q", data, off)[0]
    off += 8
    ema_price_i64 = struct.unpack_from("<q", data, off)[0]
    off += 8
    ema_conf_u64 = struct.unpack_from("<Q", data, off)[0]
    off += 8
    posted_slot = struct.unpack_from("<Q", data, off)[0]
    scale = float(10**exp_i32)
    price_human = float(price_i64) * scale
    conf_human = float(conf_u64) * scale
    ema_human = float(ema_price_i64) * scale
    return {
        "parser": "v2",
        "write_authority": write_authority,
        "verification_level": verification_level,
        "feed_id_hex": feed_id.hex(),
        "price": price_human,
        "conf": conf_human,
        "confidence": conf_human,
        "price_raw": price_i64,
        "conf_raw": conf_u64,
        "exponent": exp_i32,
        "timestamp": int(publish_time),
        "prev_publish_time": int(prev_publish_time),
        "ema_price": ema_human,
        "ema_price_raw": ema_price_i64,
        "ema_conf_raw": ema_conf_u64,
        "posted_slot": int(posted_slot),
        "status": 1,
    }


def _seeds_from_json_arg(raw: Any) -> List[bytes]:
    """Build PDA seed byte strings from JSON array of UTF-8 strings (strict prediction-market helper)."""
    if raw is None:
        raise ValueError("seeds must be a JSON array of strings")
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"seeds_json must be valid JSON: {e}") from e
    elif isinstance(raw, list):
        data = raw
    else:
        raise ValueError("seeds must be a JSON array string or list of string seeds")
    if not isinstance(data, list) or not data:
        raise ValueError("seeds must be a non-empty JSON array")
    out: List[bytes] = []
    for i, x in enumerate(data):
        if not isinstance(x, str):
            raise ValueError(f"seed[{i}] must be a string (UTF-8 seed bytes)")
        out.append(x.encode("utf-8"))
    return out


def _derive_pda_dict(seeds: List[bytes], program: Any) -> Dict[str, Any]:
    try:
        from solders.pubkey import Pubkey
    except ImportError as e:
        raise AdapterError("solders required for DERIVE_PDA; pip install 'ainativelang[solana]'") from e
    if not isinstance(program, Pubkey):
        program = Pubkey.from_string(str(program))
    pda, bump = Pubkey.find_program_address(seeds, program)
    return {
        "ok": True,
        "dry_run": False,
        "address": str(pda),
        "bump": int(bump),
        "program_id": str(program),
        "seeds_count": len(seeds),
    }


def _resolve_pyth_account_data(data: bytes, feed: Any, expect_update: bool) -> Dict[str, Any]:
    """Try PriceUpdateV2 first when length or flag suggests it, then legacy PriceAccount."""
    err_v2: Optional[Exception] = None
    err_leg: Optional[Exception] = None
    parsed: Optional[Dict[str, Any]] = None
    try_v2 = len(data) >= _PYTH_V2_MIN_LEN or expect_update
    if try_v2:
        try:
            parsed = _parse_pyth_price_update_v2(data)
        except Exception as e:
            err_v2 = e
    if parsed is None:
        try:
            parsed = _parse_pyth_legacy_price_account(data)
        except Exception as e:
            err_leg = e
    if parsed is not None:
        out = dict(parsed)
        out["ok"] = True
        out["dry_run"] = False
        out["feed"] = str(feed)
        out["expect_update_account"] = expect_update
        return out
    if expect_update:
        merged: Dict[str, Any] = {
            "ok": True,
            "dry_run": False,
            "feed": str(feed),
            "parsed": False,
            "expect_update_account": True,
            "parse_error_v2": str(err_v2) if err_v2 else None,
            "parse_error_legacy": str(err_leg) if err_leg else None,
            "account_data_len": len(data),
        }
        merged.update(_pyth_price_update_account_note())
        return merged
    msg = f"V2: {err_v2!s}; legacy: {err_leg!s}"
    chain = err_leg or err_v2
    raise AdapterError(
        f"GET_PYTH_PRICE: could not parse Pyth price account ({msg}). "
        "Use a valid on-chain feed, pass expect_update_account=true for V2 push feeds, or call "
        "solana.HERMES_FALLBACK with the 64-char feed_id_hex from the Pyth price-feed id list (Hermes / docs) "
        f"for an off-chain quote (AINL_PYTH_HERMES_URL defaults to https://hermes.pyth.network)."
    ) from chain


def _hermes_latest_price_dict(feed_hex: str) -> Dict[str, Any]:
    """GET Hermes ``/v2/updates/price/latest`` — base URL from ``AINL_PYTH_HERMES_URL`` or ``https://hermes.pyth.network``."""
    fh = (feed_hex or "").strip().lower().removeprefix("0x")
    if len(fh) != 64 or any(c not in "0123456789abcdef" for c in fh):
        raise ValueError("feed_id_hex must be 64 hex characters (32-byte Pyth feed id)")
    base = _hermes_api_base()
    url = f"{base.rstrip('/')}/v2/updates/price/latest?ids%5B%5D={fh}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Hermes HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Hermes request failed: {e}") from e
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Hermes returned non-JSON: {e}") from e
    parsed = payload.get("parsed")
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("Hermes response missing parsed[] price data")
    row = parsed[0]
    price_obj = row.get("price") or {}
    try:
        price_i = int(str(price_obj.get("price", "0")))
        conf_i = int(str(price_obj.get("conf", "0")))
        expo = int(price_obj.get("expo", 0))
        pub_t = int(price_obj.get("publish_time", 0))
    except (TypeError, ValueError) as e:
        raise ValueError(f"Hermes parsed price fields invalid: {e}") from e
    scale = float(10**expo)
    price_human = float(price_i) * scale
    conf_human = float(conf_i) * scale
    return {
        "ok": True,
        "dry_run": False,
        "parser": "hermes",
        "source": "hermes",
        "feed_id_hex": fh,
        "hermes_base": base,
        "hermes_url": url.split("?")[0],
        "price": price_human,
        "conf": conf_human,
        "confidence": conf_human,
        "price_raw": price_i,
        "conf_raw": conf_i,
        "exponent": expo,
        "timestamp": pub_t,
        "status": 1,
    }


def _set_compute_unit_price_ix(micro_lamports: int):
    """Build SetComputeUnitPrice instruction (discriminator 3 + u64 LE)."""
    if micro_lamports <= 0:
        raise ValueError("micro_lamports must be positive")
    try:
        from solders.compute_budget import set_compute_unit_price

        return set_compute_unit_price(micro_lamports)
    except Exception:
        try:
            from solders.instruction import Instruction
            from solders.pubkey import Pubkey

            cb = Pubkey.from_string("ComputeBudget111111111111111111111111111111")
            data = bytes([3]) + int(micro_lamports).to_bytes(8, "little", signed=False)
            return Instruction(program_id=cb, accounts=[], data=data)
        except ImportError as e:
            raise AdapterError(
                "solders required for ComputeBudget priority fee; pip install 'ainativelang[solana]'"
            ) from e


class SolanaAdapter(BlockchainAdapterBase):
    def __init__(self) -> None:
        self._client = None
        self._async_client = None

    @property
    def chain_family(self) -> str:
        return "solana"

    def _client_sync(self):
        if self._client is not None:
            return self._client
        try:
            from solana.rpc.api import Client
        except ImportError as e:
            raise AdapterError(
                "The 'solana' package is not installed. For live RPC calls install optional deps: "
                "pip install 'ainativelang[solana]'"
            ) from e
        try:
            self._client = Client(_rpc_url())
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="Client()")) from e
        return self._client

    def _async_client_get(self):
        if self._async_client is not None:
            return self._async_client
        try:
            from solana.rpc.async_api import AsyncClient
        except ImportError as e:
            raise AdapterError(
                "Async Solana client requires 'solana' with async_api; pip install 'ainativelang[solana]'"
            ) from e
        try:
            self._async_client = AsyncClient(_rpc_url())
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="AsyncClient()")) from e
        return self._async_client

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").upper()
        if verb not in SOLANA_VERBS:
            raise AdapterError(
                f"solana: unknown verb {target!r}. "
                f"Supported verbs: {', '.join(SOLANA_VERBS)}. "
                "See docs/emitters/README.md and adapters/solana.py module docstring. "
                "Future: blockchain.solana.VERB or evm.* may be supported via adapters/blockchain_base.py "
                "(see comment template)."
            )
        if verb == "GET_ACCOUNT":
            return self._get_account(args, context)
        if verb == "GET_BALANCE":
            return self._get_balance(args, context)
        if verb == "GET_TOKEN_ACCOUNTS":
            return self._get_token_accounts(args, context)
        if verb == "GET_PROGRAM_ACCOUNTS":
            return self._get_program_accounts(args, context)
        if verb == "GET_SIGNATURES_FOR_ADDRESS":
            return self._get_signatures_for_address(args, context)
        if verb == "GET_LATEST_BLOCKHASH":
            return self._get_latest_blockhash(args, context)
        if verb == "GET_PYTH_PRICE":
            return self._get_pyth_price(args, context)
        if verb == "HERMES_FALLBACK":
            return self._hermes_fallback(args, context)
        if verb == "GET_MARKET_STATE":
            return self._get_market_state(args, context)
        if verb == "DERIVE_PDA":
            return self._derive_pda(args, context)
        if verb == "TRANSFER":
            return self._transfer_sol(args, context)
        if verb == "TRANSFER_SPL":
            return self._transfer_spl(args, context)
        if verb == "INVOKE":
            return self._invoke(args, context)
        if verb == "SIMULATE_EVENTS":
            return self._simulate_events(args)
        raise AdapterError("solana: internal dispatch error (unexpected verb after validation).")

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        """Async-first reads via ``AsyncClient``; mutating verbs run in a worker thread to avoid blocking."""
        verb = str(target or "").upper()
        if verb not in SOLANA_VERBS:
            raise AdapterError(
                f"solana: unknown verb {target!r}. "
                f"Supported verbs: {', '.join(SOLANA_VERBS)}. "
                "See docs/emitters/README.md and adapters/solana.py module docstring. "
                "Future: blockchain.solana.VERB or evm.* may be supported via adapters/blockchain_base.py "
                "(see comment template)."
            )
        if verb == "GET_ACCOUNT":
            return await self._get_account_async(args, context)
        if verb == "GET_BALANCE":
            return await self._get_balance_async(args, context)
        if verb == "GET_TOKEN_ACCOUNTS":
            return await self._get_token_accounts_async(args, context)
        if verb == "GET_PROGRAM_ACCOUNTS":
            return await self._get_program_accounts_async(args, context)
        if verb == "GET_SIGNATURES_FOR_ADDRESS":
            return await self._get_signatures_for_address_async(args, context)
        if verb == "GET_LATEST_BLOCKHASH":
            return await self._get_latest_blockhash_async(args, context)
        if verb == "GET_PYTH_PRICE":
            return await self._get_pyth_price_async(args, context)
        if verb == "HERMES_FALLBACK":
            return await asyncio.to_thread(self._hermes_fallback, args, context)
        if verb == "GET_MARKET_STATE":
            return await self._get_market_state_async(args, context)
        if verb == "DERIVE_PDA":
            return await asyncio.to_thread(self._derive_pda, args, context)
        if verb == "TRANSFER":
            return await asyncio.to_thread(self._transfer_sol, args, context)
        if verb == "TRANSFER_SPL":
            return await asyncio.to_thread(self._transfer_spl, args, context)
        if verb == "INVOKE":
            return await asyncio.to_thread(self._invoke, args, context)
        if verb == "SIMULATE_EVENTS":
            return await asyncio.to_thread(self._simulate_events, args)
        raise AdapterError("solana: internal dispatch error (unexpected verb after validation).")

    def _pubkey(self, s: Any):
        try:
            from solders.pubkey import Pubkey
        except ImportError as e:
            raise AdapterError(
                "solders is required for Solana pubkeys; install: pip install 'ainativelang[solana]'"
            ) from e
        try:
            return Pubkey.from_string(str(s))
        except Exception as e:
            raise AdapterError(f"invalid Solana pubkey string: {s!r}") from e

    def _token_accounts_owner_mint_cap(self, args: List[Any]) -> Tuple[Any, Any, int]:
        from solana.rpc.types import TokenAccountOpts

        owner = self._pubkey(args[0])
        default_cap = int(os.environ.get("AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT") or "500")
        default_cap = max(1, min(default_cap, 10000))
        mint: Optional[Any] = None
        cap = default_cap
        if len(args) >= 2 and args[1] is not None and str(args[1]).strip():
            mint = self._pubkey(args[1])
        if len(args) >= 3:
            cap = max(1, min(int(args[2]), 10000))
        if mint is not None:
            return owner, TokenAccountOpts(mint=mint), cap
        spl_token = self._pubkey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        return owner, TokenAccountOpts(program_id=spl_token), cap

    def _get_account(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """getAccountInfo for ``pubkey``. Strict graphs require ``R solana.GET_ACCOUNT <pubkey> ->out`` — use a real
        address in the target slot, not ``_`` (contrast arity-zero reads like GET_LATEST_BLOCKHASH that use ``_``).
        """
        if not args:
            raise AdapterError("solana.GET_ACCOUNT requires pubkey")
        pk = self._pubkey(args[0])
        cli = self._client_sync()
        try:
            resp = cli.get_account_info(pk)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_account_info")) from e
        if resp.value is None:
            return {"ok": False, "error": "account_not_found", "pubkey": str(pk)}
        val = resp.value
        return {"ok": True, "pubkey": str(pk), "lamports": int(val.lamports), "owner": str(val.owner)}

    async def _get_account_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Async getAccountInfo; same strict-target rules as :meth:`_get_account`."""
        if not args:
            raise AdapterError("solana.GET_ACCOUNT requires pubkey")
        pk = self._pubkey(args[0])
        cli = self._async_client_get()
        try:
            resp = await cli.get_account_info(pk)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_account_info(async)")) from e
        if resp.value is None:
            return {"ok": False, "error": "account_not_found", "pubkey": str(pk)}
        val = resp.value
        return {"ok": True, "pubkey": str(pk), "lamports": int(val.lamports), "owner": str(val.owner)}

    def _get_balance(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_BALANCE requires pubkey")
        pk = self._pubkey(args[0])
        cli = self._client_sync()
        try:
            resp = cli.get_balance(pk)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_balance")) from e
        return {"ok": True, "pubkey": str(pk), "lamports": int(resp.value)}

    async def _get_balance_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_BALANCE requires pubkey")
        pk = self._pubkey(args[0])
        cli = self._async_client_get()
        try:
            resp = await cli.get_balance(pk)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_balance(async)")) from e
        return {"ok": True, "pubkey": str(pk), "lamports": int(resp.value)}

    def _serialize_token_account_rows(
        self, raw: Any, cap: int
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        accts: List[Dict[str, Any]] = []
        if raw:
            for item in raw:
                try:
                    pub = getattr(item, "pubkey", item)
                    acct = getattr(item, "account", None)
                    accts.append(
                        {
                            "pubkey": str(pub),
                            "account": acct.to_json()
                            if acct is not None and hasattr(acct, "to_json")
                            else str(acct),
                        }
                    )
                except Exception:
                    accts.append({"raw": str(item)})
        total = len(accts)
        truncated = total > cap
        return accts[:cap], total, truncated

    def _get_token_accounts(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_TOKEN_ACCOUNTS requires owner_pubkey [mint_pubkey] [limit]")
        owner, opts, cap = self._token_accounts_owner_mint_cap(args)
        cli = self._client_sync()
        try:
            resp = cli.get_token_accounts_by_owner_json_parsed(owner, opts)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_token_accounts_by_owner_json_parsed")) from e
        raw = resp.value
        rows, total, truncated = self._serialize_token_account_rows(raw, cap)
        out: Dict[str, Any] = {
            "ok": True,
            "owner": str(owner),
            "count": len(rows),
            "total_fetched": total,
            "truncated": truncated,
            "cap": cap,
            "accounts": rows,
        }
        if truncated:
            out["warning"] = (
                f"Response truncated to {cap} accounts (fetched {total}). "
                "Pass a mint as the second arg, lower AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT, "
                "or pass an explicit third-arg limit."
            )
        return out

    async def _get_token_accounts_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_TOKEN_ACCOUNTS requires owner_pubkey [mint_pubkey] [limit]")
        owner, opts, cap = self._token_accounts_owner_mint_cap(args)
        cli = self._async_client_get()
        try:
            resp = await cli.get_token_accounts_by_owner_json_parsed(owner, opts)
        except Exception as e:
            raise AdapterError(
                _rpc_failure_message(e, where="get_token_accounts_by_owner_json_parsed(async)")
            ) from e
        raw = resp.value
        rows, total, truncated = self._serialize_token_account_rows(raw, cap)
        out: Dict[str, Any] = {
            "ok": True,
            "owner": str(owner),
            "count": len(rows),
            "total_fetched": total,
            "truncated": truncated,
            "cap": cap,
            "accounts": rows,
        }
        if truncated:
            out["warning"] = (
                f"Response truncated to {cap} accounts (fetched {total}). "
                "Pass a mint as the second arg, lower AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT, "
                "or pass an explicit third-arg limit."
            )
        return out

    def _get_program_accounts(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        prog, filters, limit = _parse_program_accounts_args(args)
        cli = self._client_sync()
        try:
            resp = cli.get_program_accounts_json_parsed(prog, filters=filters)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_program_accounts_json_parsed")) from e
        raw = resp.value or []
        total = len(raw)
        slice_rows = raw[:limit]
        rows: List[Dict[str, Any]] = []
        for item in slice_rows:
            try:
                pub = getattr(item, "pubkey", item)
                acct = getattr(item, "account", None)
                rows.append(
                    {
                        "pubkey": str(pub),
                        "account": acct.to_json()
                        if acct is not None and hasattr(acct, "to_json")
                        else str(acct),
                    }
                )
            except Exception:
                rows.append({"raw": str(item)})
        out: Dict[str, Any] = {
            "ok": True,
            "program_id": str(prog),
            "count": len(rows),
            "total_fetched": total,
            "truncated": total > len(rows),
            "cap": limit,
            "accounts": rows,
        }
        if total > limit:
            out["warning"] = (
                f"Truncated to {limit} accounts (RPC returned {total}). "
                "Tighten filters JSON or lower AINL_SOLANA_GET_PROGRAM_ACCOUNTS_LIMIT."
            )
        return out

    async def _get_program_accounts_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        prog, filters, limit = _parse_program_accounts_args(args)
        cli = self._async_client_get()
        try:
            resp = await cli.get_program_accounts_json_parsed(prog, filters=filters)
        except Exception as e:
            raise AdapterError(
                _rpc_failure_message(e, where="get_program_accounts_json_parsed(async)")
            ) from e
        raw = resp.value or []
        total = len(raw)
        slice_rows = raw[:limit]
        rows: List[Dict[str, Any]] = []
        for item in slice_rows:
            try:
                pub = getattr(item, "pubkey", item)
                acct = getattr(item, "account", None)
                rows.append(
                    {
                        "pubkey": str(pub),
                        "account": acct.to_json()
                        if acct is not None and hasattr(acct, "to_json")
                        else str(acct),
                    }
                )
            except Exception:
                rows.append({"raw": str(item)})
        out: Dict[str, Any] = {
            "ok": True,
            "program_id": str(prog),
            "count": len(rows),
            "total_fetched": total,
            "truncated": total > len(rows),
            "cap": limit,
            "accounts": rows,
        }
        if total > limit:
            out["warning"] = (
                f"Truncated to {limit} accounts (RPC returned {total}). "
                "Tighten filters JSON or lower AINL_SOLANA_GET_PROGRAM_ACCOUNTS_LIMIT."
            )
        return out

    def _get_signatures_for_address(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_SIGNATURES_FOR_ADDRESS requires address [limit]")
        addr = self._pubkey(args[0])
        lim = 10
        if len(args) > 1:
            lim = max(1, min(int(args[1]), 1000))
        cli = self._client_sync()
        try:
            resp = cli.get_signatures_for_address(addr, limit=lim)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_signatures_for_address")) from e
        val = resp.value or []
        sigs = []
        for item in val:
            try:
                sigs.append(
                    {
                        "signature": str(item.signature),
                        "slot": getattr(item, "slot", None),
                        "err": getattr(item, "err", None),
                    }
                )
            except Exception:
                sigs.append({"raw": str(item)})
        return {"ok": True, "address": str(addr), "limit": lim, "count": len(sigs), "signatures": sigs}

    async def _get_signatures_for_address_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("solana.GET_SIGNATURES_FOR_ADDRESS requires address [limit]")
        addr = self._pubkey(args[0])
        lim = 10
        if len(args) > 1:
            lim = max(1, min(int(args[1]), 1000))
        cli = self._async_client_get()
        try:
            resp = await cli.get_signatures_for_address(addr, limit=lim)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_signatures_for_address(async)")) from e
        val = resp.value or []
        sigs = []
        for item in val:
            try:
                sigs.append(
                    {
                        "signature": str(item.signature),
                        "slot": getattr(item, "slot", None),
                        "err": getattr(item, "err", None),
                    }
                )
            except Exception:
                sigs.append({"raw": str(item)})
        return {"ok": True, "address": str(addr), "limit": lim, "count": len(sigs), "signatures": sigs}

    def _get_latest_blockhash(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """JSON-RPC getLatestBlockhash: recent blockhash + last valid block height for transaction building.

        In ``.ainl``, use ``_`` as the target token when no primary argument is needed (strict parser requires
        ``adapter target ->out``). Pair with INVOKE (or TRANSFER) when composing transactions; under AINL_DRY_RUN=1,
        mutating verbs still return mock sigs while this returns a mock blockhash for end-to-end rehearsal.

        Read-only. With AINL_DRY_RUN=1 returns a mock blockhash (no network); unset for live RPC.
        """
        _ = args, context
        if _is_dry_run():
            return {
                "ok": True,
                "dry_run": True,
                "blockhash": _mock_latest_blockhash(),
                "last_valid_block_height": None,
                "note": "AINL_DRY_RUN: mock blockhash (no RPC). Unset dry-run for a live latest blockhash.",
            }
        cli = self._client_sync()
        try:
            resp = cli.get_latest_blockhash()
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_latest_blockhash")) from e
        v = resp.value
        bh = getattr(v, "blockhash", v)
        lvh = getattr(v, "last_valid_block_height", None)
        return {
            "ok": True,
            "dry_run": False,
            "blockhash": str(bh),
            "last_valid_block_height": int(lvh) if lvh is not None else None,
        }

    async def _get_latest_blockhash_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Async getLatestBlockhash via AsyncClient (same semantics as _get_latest_blockhash).

        Use the blockhash with INVOKE/TRANSFER flows when building transactions off the async path.
        """
        _ = args, context
        if _is_dry_run():
            return {
                "ok": True,
                "dry_run": True,
                "blockhash": _mock_latest_blockhash(),
                "last_valid_block_height": None,
                "note": "AINL_DRY_RUN: mock blockhash (no RPC). Unset dry-run for a live latest blockhash.",
            }
        cli = self._async_client_get()
        try:
            resp = await cli.get_latest_blockhash()
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="get_latest_blockhash(async)")) from e
        v = resp.value
        bh = getattr(v, "blockhash", v)
        lvh = getattr(v, "last_valid_block_height", None)
        return {
            "ok": True,
            "dry_run": False,
            "blockhash": str(bh),
            "last_valid_block_height": int(lvh) if lvh is not None else None,
        }

    def _get_pyth_price(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Read a Pyth on-chain price feed (legacy PriceAccount or PriceUpdateV2). Pair with INVOKE / HERMES_FALLBACK."""
        _ = context
        if not args:
            raise AdapterError("solana.GET_PYTH_PRICE requires price_feed_pubkey [expect_update_account]")
        feed = self._pubkey(args[0])
        expect_update = _truthy_arg(args[1]) if len(args) > 1 else False
        if _is_dry_run():
            out: Dict[str, Any] = {
                "ok": True,
                "dry_run": True,
                "parser": "v2" if expect_update else "legacy",
                "feed": str(feed),
                "expect_update_account": expect_update,
                "price": 100.0,
                "conf": 0.05,
                "confidence": 0.05,
                "exponent": -5,
                "status": 1,
                "timestamp": 1700000000 if expect_update else None,
                "timestamp_note": "legacy PriceAccount has no unix timestamp; use publish_slot / valid_slot vs cluster"
                if not expect_update
                else "dry-run mock timestamp for V2",
                "valid_slot": 0,
                "publish_slot": 0,
                "note": "AINL_DRY_RUN: mock Pyth fields (no RPC).",
            }
            if expect_update:
                out.update(_pyth_price_update_account_note())
            return out
        cli = self._client_sync()
        try:
            resp = cli.get_account_info(feed)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="GET_PYTH_PRICE get_account_info")) from e
        val = resp.value
        if val is None:
            return {"ok": False, "error": "account_not_found", "feed": str(feed)}
        data = bytes(val.data)
        return _resolve_pyth_account_data(data, feed, expect_update)

    async def _get_pyth_price_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        _ = context
        if not args:
            raise AdapterError("solana.GET_PYTH_PRICE requires price_feed_pubkey [expect_update_account]")
        feed = self._pubkey(args[0])
        expect_update = _truthy_arg(args[1]) if len(args) > 1 else False
        if _is_dry_run():
            out: Dict[str, Any] = {
                "ok": True,
                "dry_run": True,
                "parser": "v2" if expect_update else "legacy",
                "feed": str(feed),
                "expect_update_account": expect_update,
                "price": 100.0,
                "conf": 0.05,
                "confidence": 0.05,
                "exponent": -5,
                "status": 1,
                "timestamp": 1700000000 if expect_update else None,
                "timestamp_note": "legacy PriceAccount has no unix timestamp; use publish_slot / valid_slot vs cluster"
                if not expect_update
                else "dry-run mock timestamp for V2",
                "valid_slot": 0,
                "publish_slot": 0,
                "note": "AINL_DRY_RUN: mock Pyth fields (no RPC).",
            }
            if expect_update:
                out.update(_pyth_price_update_account_note())
            return out
        cli = self._async_client_get()
        try:
            resp = await cli.get_account_info(feed)
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="GET_PYTH_PRICE get_account_info(async)")) from e
        val = resp.value
        if val is None:
            return {"ok": False, "error": "account_not_found", "feed": str(feed)}
        data = bytes(val.data)
        return _resolve_pyth_account_data(data, feed, expect_update)

    def _derive_pda(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Derive a program-derived address from UTF-8 string seeds (prediction-market PDAs, vaults).
        Useful for deriving prediction market PDAs, vaults, or escrow accounts.
        """
        _ = context
        if len(args) < 2:
            raise AdapterError("solana.DERIVE_PDA requires seeds_json program_id")
        try:
            seeds = _seeds_from_json_arg(args[0])
        except ValueError as e:
            raise AdapterError(f"solana.DERIVE_PDA: {e}") from e
        if _is_dry_run():
            return {
                "ok": True,
                "dry_run": True,
                "address": "DRYRUN_PDA_" + secrets.token_hex(16),
                "bump": 254,
                "program_id": str(args[1]).strip(),
                "seeds_count": len(seeds),
                "note": "AINL_DRY_RUN: mock PDA (no derivation).",
            }
        program = self._pubkey(args[1])
        try:
            return _derive_pda_dict(seeds, program)
        except Exception as e:
            raise AdapterError(f"solana.DERIVE_PDA: {e}") from e

    def _hermes_fallback(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Off-chain Hermes latest price for a feed id (hex); use when on-chain parse fails or for redundancy."""
        _ = context
        if not args:
            raise AdapterError("solana.HERMES_FALLBACK requires feed_id_hex")
        feed_hex = str(args[0]).strip()
        if _is_dry_run():
            fh = feed_hex.lower().removeprefix("0x")[:64]
            return {
                "ok": True,
                "dry_run": True,
                "parser": "hermes",
                "source": "hermes",
                "hermes_base": _hermes_api_base(),
                "feed_id_hex": fh or "0" * 64,
                "price": 123.45,
                "conf": 0.01,
                "confidence": 0.01,
                "exponent": -8,
                "timestamp": 1700000000,
                "note": "AINL_DRY_RUN: mock Hermes quote (no HTTP).",
            }
        try:
            return _hermes_latest_price_dict(feed_hex)
        except ValueError as e:
            raise AdapterError(f"solana.HERMES_FALLBACK: {e}") from e

    def _get_market_state(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """PDA/market account read; same as GET_ACCOUNT with ``read_as`` marker for prediction-market workflows."""
        out = self._get_account(args, context)
        if isinstance(out, dict):
            o = dict(out)
            o["read_as"] = "market_state"
            return o
        return out

    async def _get_market_state_async(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        out = await self._get_account_async(args, context)
        if isinstance(out, dict):
            o = dict(out)
            o["read_as"] = "market_state"
            return o
        return out

    def _transfer_sol(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if len(args) < 2:
            raise AdapterError("solana.TRANSFER requires destination_pubkey lamports")
        lamports = int(args[1])
        if _is_dry_run():
            return _dry_run_mutation_envelope(
                "TRANSFER",
                to=str(args[0]).strip(),
                lamports=lamports,
                fee_lamports_estimate=5000,
            )
        dest = self._pubkey(args[0])
        kp = _resolve_keypair(context)
        if kp is None:
            raise AdapterError(
                "solana.TRANSFER requires a keypair: set AINL_SOLANA_KEYPAIR_JSON, "
                "or frame context _solana_keypair_json, or enable AINL_DRY_RUN=1 for simulation. "
                + _KEYPAIR_HINT
            )
        try:
            from solders.message import Message
            from solders.system_program import TransferParams, transfer
            from solders.transaction import Transaction
            from solana.rpc.types import TxOpts
        except ImportError as e:
            raise AdapterError("solders/solana transaction types missing; pip install 'ainativelang[solana]'") from e

        src = kp.pubkey()
        ix = transfer(TransferParams(from_pubkey=src, to_pubkey=dest, lamports=lamports))
        cli = self._client_sync()
        try:
            recent = cli.get_latest_blockhash()
            bh = recent.value.blockhash
            msg = Message.new_with_blockhash([ix], src, bh)
            tx = Transaction.new_unsigned(msg)
            tx.sign([kp], bh)
            send = cli.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_preflight=False))
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="TRANSFER send_raw_transaction")) from e
        sig = str(send.value) if send.value is not None else None
        return {"ok": True, "dry_run": False, "signature": sig, "to": str(dest), "lamports": lamports}

    def _transfer_spl(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if len(args) < 5:
            raise AdapterError("solana.TRANSFER_SPL requires mint source_ata dest_ata owner amount [decimals]")
        amount = int(args[4])
        decimals = int(args[5]) if len(args) > 5 else 9
        if _is_dry_run():
            return _dry_run_mutation_envelope(
                "TRANSFER_SPL",
                mint=str(args[0]).strip(),
                amount=amount,
                decimals=decimals,
            )
        mint = self._pubkey(args[0])
        src_ata = self._pubkey(args[1])
        dst_ata = self._pubkey(args[2])
        owner = self._pubkey(args[3])
        try:
            from spl.token.instructions import TransferCheckedParams, transfer_checked
            from solders.message import Message
            from solders.transaction import Transaction
            from solana.rpc.types import TxOpts
        except ImportError:
            warnings.warn(
                "SPL helpers not available (install spl.token or use INVOKE with raw instruction).",
                RuntimeWarning,
                stacklevel=2,
            )
            raise AdapterError(
                "solana.TRANSFER_SPL needs spl.token.instructions; ensure 'ainativelang[solana]' install is complete"
            )
        kp = _resolve_keypair(context)
        if kp is None:
            raise AdapterError(
                "solana.TRANSFER_SPL requires AINL_SOLANA_KEYPAIR_JSON / _solana_keypair_json, or AINL_DRY_RUN=1. "
                + _KEYPAIR_HINT
            )
        token_program = self._pubkey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        ix = transfer_checked(
            TransferCheckedParams(
                program_id=token_program,
                source=src_ata,
                mint=mint,
                dest=dst_ata,
                owner=owner,
                amount=amount,
                decimals=decimals,
                signers=[],
            )
        )
        fee_payer = kp.pubkey()
        cli = self._client_sync()
        try:
            recent = cli.get_latest_blockhash()
            bh = recent.value.blockhash
            msg = Message.new_with_blockhash([ix], fee_payer, bh)
            tx = Transaction.new_unsigned(msg)
            tx.sign([kp], bh)
            send = cli.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_preflight=False))
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="TRANSFER_SPL send_raw_transaction")) from e
        sig = str(send.value) if send.value is not None else None
        return {"ok": True, "signature": sig, "mint": str(mint), "amount": amount}

    def _invoke(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Raw program invoke; optional trailing int is **micro-lamports per compute unit** (SetComputeUnitPrice).

        Values are **not** whole-lamport tips — tune lower for cost control, higher for settlement/trades in busy slots.
        """
        if len(args) < 2:
            raise AdapterError(
                "solana.INVOKE requires program_id instruction_bytes_b64 [accounts_json] [priority_fee_microlamports]"
            )
        try:
            raw = base64.b64decode(str(args[1]))
        except Exception as e:
            raise AdapterError(f"solana.INVOKE: invalid base64 instruction data: {e}") from e
        accounts: Sequence[Any] = []
        priority_micro = 0
        tail = args[2:]

        if len(tail) == 0:
            pass
        elif len(tail) == 1:
            if _is_int_like(tail[0]):
                priority_micro = max(0, int(tail[0]))
            elif tail[0] is not None and str(tail[0]).strip():
                try:
                    accounts = json.loads(str(tail[0])) if isinstance(tail[0], str) else tail[0]
                except json.JSONDecodeError as e:
                    raise AdapterError(f"solana.INVOKE: accounts_json must be valid JSON: {e}") from e
        else:
            if tail[0] is not None and str(tail[0]).strip():
                try:
                    accounts = json.loads(str(tail[0])) if isinstance(tail[0], str) else tail[0]
                except json.JSONDecodeError as e:
                    raise AdapterError(f"solana.INVOKE: accounts_json must be valid JSON: {e}") from e
            if len(tail) >= 2 and _is_int_like(tail[1]):
                priority_micro = max(0, int(tail[1]))

        if _is_dry_run():
            acct_list = accounts if isinstance(accounts, list) else []
            env = _dry_run_mutation_envelope(
                "INVOKE",
                program_id=str(args[0]).strip(),
                instruction_len=len(raw),
                accounts=acct_list,
            )
            if priority_micro > 0:
                env["priority_fee_microlamports"] = priority_micro
            return env
        program_id = self._pubkey(args[0])
        try:
            from solders.instruction import AccountMeta, Instruction
            from solders.message import Message
            from solders.transaction import Transaction
            from solana.rpc.types import TxOpts
        except ImportError as e:
            raise AdapterError("solders/solana types required for INVOKE; pip install 'ainativelang[solana]'") from e
        metas = []
        if isinstance(accounts, list):
            for a in accounts:
                if not isinstance(a, dict):
                    continue
                pk = self._pubkey(a.get("pubkey") or a.get("address"))
                metas.append(
                    AccountMeta(
                        pubkey=pk,
                        is_signer=bool(a.get("is_signer", False)),
                        is_writable=bool(a.get("is_writable", False)),
                    )
                )
        ix = Instruction(program_id=program_id, accounts=metas, data=raw)
        kp = _resolve_keypair(context)
        if kp is None:
            raise AdapterError(
                "solana.INVOKE requires a fee-payer keypair (AINL_SOLANA_KEYPAIR_JSON or _solana_keypair_json), "
                "or AINL_DRY_RUN=1. " + _KEYPAIR_HINT
            )
        fee_payer = kp.pubkey()
        cli = self._client_sync()
        try:
            recent = cli.get_latest_blockhash()
            bh = recent.value.blockhash
            ixs = []
            if priority_micro > 0:
                ixs.append(_set_compute_unit_price_ix(priority_micro))
            ixs.append(ix)
            msg = Message.new_with_blockhash(ixs, fee_payer, bh)
            tx = Transaction.new_unsigned(msg)
            tx.sign([kp], bh)
            send = cli.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_preflight=False))
        except Exception as e:
            raise AdapterError(_rpc_failure_message(e, where="INVOKE send_raw_transaction")) from e
        sig = str(send.value) if send.value is not None else None
        out: Dict[str, Any] = {"ok": True, "signature": sig, "program_id": str(program_id)}
        if priority_micro > 0:
            out["priority_fee_microlamports"] = priority_micro
        return out

    def _simulate_events(self, args: List[Any]) -> Dict[str, Any]:
        prog = str(args[0]) if args else "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        return {
            "ok": True,
            "mode": "simulation",
            "program_id": prog,
            "note": "In-process event listen simulation (no websocket); use logsSubscribe in production.",
            "events": [
                {
                    "slot": 0,
                    "signature": "SIMULATED",
                    "logs": [f"Program {prog} invoke [1]", "Program log: simulated listener"],
                }
            ],
        }
