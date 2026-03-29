# Solana strict graphs — quickstart (AINL v1.3.3)

Use this page when you want **deterministic prediction-market style workflows** on Solana: PDAs, Pyth or Hermes prices, and `INVOKE` / `TRANSFER_SPL` with priority fees. The canonical end-to-end example is **`examples/prediction_market_demo.ainl`**.

## Installation

```bash
pip install "ainativelang[solana]"
```

The `[solana]` extra pulls `solana` and `solders` for live RPC and pubkey parsing. Dry-run paths (`AINL_DRY_RUN=1`) can exercise many graphs without a funded keypair.

## Important environment variables

| Variable | Role |
|----------|------|
| `AINL_SOLANA_RPC_URL` | JSON-RPC endpoint (default: `https://api.devnet.solana.com`). |
| `AINL_SOLANA_KEYPAIR_JSON` | Path to keypair JSON or JSON array of 64 bytes (mutating live txs). Never commit secrets. |
| `AINL_DRY_RUN` | When truthy (`1`, `true`), mutating verbs return **simulation envelopes** without sending transactions; `GET_LATEST_BLOCKHASH` and Pyth/Hermes mocks avoid network where documented. |
| `AINL_PYTH_HERMES_URL` | Optional base URL for **HERMES_FALLBACK** (default Hermes origin if unset). |

Frame overrides (e.g. `_solana_keypair_json`) are documented in `adapters/solana.py`.

## Compile and emit a client

From the repo root (or with `ainl` on your PATH):

```bash
python scripts/validate_ainl.py examples/prediction_market_demo.ainl --strict --emit solana-client -o solana_client.py
# Alias:
python scripts/validate_ainl.py examples/solana_demo.ainl --strict --emit blockchain-client -o solana_client.py
```

The emitted module embeds **IR + RuntimeEngine** and matches the discoverability text in the generated docstring.

## Dry-run first

1. `export AINL_DRY_RUN=1`
2. Run `ainl run` on your `.ainl` or execute the emitted `solana_client.py`.
3. Inspect structured outputs (mock blockhash, Hermes/Pyth-shaped dicts, `DRYRUN_*` signatures) before pointing at mainnet or real keys.

## Key prediction market patterns

- **DERIVE_PDA** — Use **single-quoted JSON** for seeds: `'["market","ID"]'` is one token; inner `"` stay literal.
- **GET_PYTH_PRICE** — On-chain legacy `PriceAccount` or **PriceUpdateV2**; optional second arg prefers V2 when ambiguous.
- **HERMES_FALLBACK** — Off-chain quote by 64-char hex **feed_id** (redundant with Pyth when RPC is flaky).
- **Conditional payout** — Branch on price / threshold (`If` → labels), then **INVOKE** with `[]` accounts and a trailing **priority fee** int (micro-lamports per CU), e.g. `5000`.

See **`examples/prediction_market_demo.ainl`** comments for the full pattern.

## For AI agents exploring the codebase

Example prompts you can use when searching or asking tools:

- **"Where is the Solana adapter and what verbs does v1.3.3 support for prediction markets?"** → `adapters/solana.py` module docstring (DISCOVERABILITY section).
- **"Show how to emit a runnable Python client from a strict Solana graph."** → `docs/emitters/README.md` Solana section, **`--emit solana-client`**.
- **"What is the minimal strict example for Pyth + Hermes + INVOKE with priority fees?"** → `examples/prediction_market_demo.ainl`.

Related: **`docs/emitters/README.md`** (emitter details), **`examples/README.md`** (Solana one-liner).

## How the prediction market community team can contribute

- **Extend the demo with real markets:** Fork `examples/prediction_market_demo.ainl` and add your own market PDAs, Pyth feed IDs, and settlement program `INVOKE` calls (keep comments clear about which cluster and program version you use).
- **Dry-run and share artifacts:** Run your graphs with `AINL_DRY_RUN=1` on devnet first and share strict-compile success notes or example dry-run envelopes (redacted) in issues or docs PRs.
- **Propose additive Solana verbs:** Open issues/PRs suggesting new lightweight verbs (e.g., reusable PDA patterns, richer Pyth pull helpers) that stay additive-only and follow the existing Solana adapter style.
- **Report cost and performance:** When you run production-ish flows on devnet/mainnet with priority fees, share observations on slot inclusion, micro-lamports/CU choices, and overall fee patterns so examples and docs can be tuned.
- **Contribute composability workflows:** Add examples that show DFlow/Kalshi-style books or sentiment-signal agents routing into on-chain trades using `INVOKE` / `TRANSFER_SPL`, keeping graphs strict-valid and dry-run friendly.

All contributions must stay additive and non-breaking to preserve Hyperspace compatibility and strict graph guarantees.
