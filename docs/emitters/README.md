# Emitters

Use this section to understand how AINL expands into downstream artifacts such as APIs, schemas, infrastructure, and application surfaces.

## Current anchors

- [`TARGETS_ROADMAP.md`](../runtime/TARGETS_ROADMAP.md) — target/runtime support map
- [`../reference/TOOL_API.md`](../reference/TOOL_API.md) — compile/validate/emit loop contract

## Hyperspace agent emitter

Emit a **single-file Python agent** that embeds the compiled IR and runs it with `RuntimeEngine`, registering local **`vector_memory`** and **`tool_registry`** adapters and an optional `hyperspace_sdk` import stub.

**Command** (from repo root, typical):

```bash
python3 scripts/validate_ainl.py path/to/workflow.ainl --strict --emit hyperspace -o hyperspace_agent.py
```

`ainl-validate` exposes the same `--emit hyperspace` when invoked as the validate entrypoint (see root `README.md`).

**Run the emitted file** from a working tree that contains `runtime/engine.py` and `adapters/` (usually **repo root**), e.g. `python3 hyperspace_agent.py`, so imports resolve.

**Trajectory:** emitted agents honor `AINL_LOG_TRAJECTORY` / runtime trajectory hooks; JSONL is written relative to the process cwd (see [`../trajectory.md`](../trajectory.md)).

**Happy-path demo:** `examples/hyperspace_demo.ainl` — compare with `ainl run … --enable-adapter vector_memory --enable-adapter tool_registry --log-trajectory` as in root `README.md`.

**Optional (not registered by this emitter):** tiered repo context via **`code_context`** — see [`../adapters/CODE_CONTEXT.md`](../adapters/CODE_CONTEXT.md) and `examples/code_context_demo.ainl`; enable with `--enable-adapter code_context` when running graphs that call it.

## Solana client emitter (`solana-client` / `blockchain-client`)

**v1.7.1 / latest Solana onboarding — fastest start is [docs/solana_quickstart.md](../solana_quickstart.md) + [examples/prediction_market_demo.ainl](../../examples/prediction_market_demo.ainl).**

Emit a **single-file Python runner** that embeds the compiled IR (base64) and registers **`core`**, **`vector_memory`**, **`tool_registry`**, and **`solana`** (`adapters/solana.SolanaAdapter`), same structural pattern as the Hyperspace emitter but **without** `hyperspace_sdk`.

### Quick Start for Solana

1. **Install optional RPC deps** (once per venv):

   ```bash
   pip install 'ainativelang[solana]'
   ```

2. **Environment** (read-only demos work on default devnet):

   - `AINL_SOLANA_RPC_URL` — default `https://api.devnet.solana.com` if unset.
   - `AINL_DRY_RUN=1` — mutating graph steps return **mock signatures**; no transactions sent.
   - `AINL_SOLANA_KEYPAIR_JSON` — path to a JSON keypair file **or** inline JSON byte array (only when sending real txs; never commit it).

3. **Compile and emit** the standalone runner:

   ```bash
   python3 scripts/validate_ainl.py examples/solana_demo.ainl --strict --emit solana-client -o solana_client.py
   python3 scripts/validate_ainl.py examples/prediction_market_demo.ainl --strict --emit solana-client -o solana_pm_client.py
   ```

4. **Run** from the repo root (so `runtime/` and `adapters/` resolve):

   ```bash
   export AINL_DRY_RUN=1
   python3 solana_client.py
   AINL_SOLANA_DEMO_PREVIEW=1 python3 solana_client.py   # IR summary + run
   ```

- **Solana verbs** (all listed; read-only steps use live RPC unless `AINL_DRY_RUN=1`, which mocks mutating txs and `GET_LATEST_BLOCKHASH`): `GET_ACCOUNT`, `GET_BALANCE`, `GET_TOKEN_ACCOUNTS`, `GET_PROGRAM_ACCOUNTS`, `GET_SIGNATURES_FOR_ADDRESS`, `GET_LATEST_BLOCKHASH`, `GET_PYTH_PRICE`, `HERMES_FALLBACK`, `GET_MARKET_STATE`, `DERIVE_PDA`, `TRANSFER`, `TRANSFER_SPL`, `INVOKE`, `SIMULATE_EVENTS`.

- **Real transactions:** set `AINL_SOLANA_KEYPAIR_JSON` and remove `AINL_DRY_RUN=1`. Always test on devnet first.

- **Strict `R` shape:** each step is `R solana.<VERB> <target> ... ->out`. When a verb has no primary argument, use `_` as the target token (e.g. `R solana.GET_LATEST_BLOCKHASH _ ->bh`).

- **General blockchain development:** Start with `--emit solana-client` or `blockchain-client`. Extend via [`adapters/blockchain_base.py`](../adapters/blockchain_base.py) (EVM template included as comment). Keep all changes additive to preserve Hyperspace and other targets.

### Prediction markets on Solana

- **Env:** same as Quick Start (`AINL_SOLANA_RPC_URL`, `AINL_DRY_RUN=1` for rehearsal, `AINL_SOLANA_KEYPAIR_JSON` when sending real settlement/trades).
- **Pyth on-chain + Hermes:** `GET_PYTH_PRICE` tries **PriceUpdateV2** (push/receiver feeds, ~134+ bytes) then **legacy PriceAccount**; the result includes `parser: "legacy"` or `"v2"`. For **off-chain** redundancy or when RPC is flaky, `R solana.HERMES_FALLBACK <feed_id_hex_64> ->hq` calls Hermes (`AINL_PYTH_HERMES_URL` optional base override). **Cost:** use on-chain reads when you need composability; Hermes for spot checks without RPC load.
- **Reliability:** for highest reliability combine on-chain V2 parsing with **HERMES_FALLBACK** as a fallback path (same feed id hex from the Pyth price-feed list).
- **PDA helper:** `R solana.DERIVE_PDA '["market","<market_id>"]' <program_id> ->pda` derives a market/vault PDA from UTF-8 string seeds (prediction programs); same dry-run mock pattern as other reads.
- **Market PDAs:** `R solana.GET_MARKET_STATE <market_pubkey> ->mst` is a thin wrapper over account fetch (`read_as: market_state`) for prediction/outcome accounts.
- **Priority fees (cost control):** `R solana.INVOKE <program> <ix_b64> <accounts_json> <priority_microlamports> ->sig` sets **SetComputeUnitPrice** in **micro-lamports per CU** — raise only when you need inclusion (resolution/payout bursts), keep lower for routine probes to control fees.
- **Resolution → payout flow:** fetch `GET_PYTH_PRICE` / `GET_MARKET_STATE`, branch in IR (`If` on thresholds), then `INVOKE` settlement with an explicit priority fee when landing real payouts; rehearse with `AINL_DRY_RUN=1` first.
- **Composability:** route liquidity or signals off-chain (DFlow, Kalshi-tokenized books, sentiment agents) and land deterministic legs on-chain via `INVOKE` / `TRANSFER`; keep graphs strict-valid and dry-run first.
- **Compile demo:** `python3 scripts/validate_ainl.py examples/prediction_market_demo.ainl --strict --emit solana-client -o solana_client.py` — or `ainl compile examples/prediction_market_demo.ainl --strict --emit solana-client -o solana_client.py`

**Commands**

```bash
python3 scripts/validate_ainl.py examples/solana_demo.ainl --strict --emit solana-client -o solana_client.py
# alias:
python3 scripts/validate_ainl.py examples/solana_demo.ainl --strict --emit blockchain-client -o solana_client.py
ainl compile examples/solana_demo.ainl --emit solana-client -o solana_client.py
```

**Optional dependencies:** `pip install 'ainativelang[solana]'` (installs `solana` and `solders`). Without them, importing the adapter warns at runtime; **read-only** paths like `R solana.GET_ACCOUNT ...` need those packages for live RPC.

**Environment:** default RPC is **devnet** (`https://api.devnet.solana.com`) unless `AINL_SOLANA_RPC_URL` is set. Key material: `AINL_SOLANA_KEYPAIR_JSON` (path or JSON bytes) or frame field `_solana_keypair_json` — never commit secrets. Use `AINL_DRY_RUN=1` to simulate sends.

**Emitted `__main__`:** set `AINL_SOLANA_DEMO_PREVIEW=1` to log label/step counts and the first step before `run_ainl()` executes the full entry label.

**DSL:** dotted verbs `R solana.<VERB> ...`, e.g. `GET_ACCOUNT`, `GET_BALANCE`, `GET_TOKEN_ACCOUNTS`, `GET_PROGRAM_ACCOUNTS`, `GET_SIGNATURES_FOR_ADDRESS`, `GET_LATEST_BLOCKHASH`, `GET_PYTH_PRICE`, `HERMES_FALLBACK`, `GET_MARKET_STATE`, `DERIVE_PDA`, `TRANSFER`, `TRANSFER_SPL`, `INVOKE`, `SIMULATE_EVENTS` (see `adapters/solana.py`). Policy/registry name **`solana`** is the first **blockchain.solana**-family adapter; strict DSL keeps the `solana.` prefix (first-dot split).

## ArmaraOS Hand package emitter (`armaraos`)

Emit a **directory** consumable by **ArmaraOS** / **openfang-hands**: manifest, compiled IR, security hints, and a short README.

**Command** (repo root, typical):

```bash
ainl emit path/to/workflow.ainl --target armaraos -o ./workflow_hand
```

**Artifacts:**

| File | Role |
|------|------|
| `HAND.toml` | `[hand]` table: `id`, `name`, `version`, `ainl_ir_version`, **`schema_version`** (contract **`1`** today), `entrypoint`, metadata, config/security stubs |
| `<stem>.ainl.json` | Compiled IR JSON plus top-level **`schema_version`** (**emitter adds**; the in-memory IR passed into the emitter is **not** mutated) |
| `security.json` | Policy object; **`schema_version`** is the **first** key, then `version`, `sandbox`, `wasm_config`, **`capability_declarations.adapters`**, etc. |
| `README.md` | Operator summary |

**Why `schema_version`:** the Rust **openfang-hands** loader and **`openfang hand validate`** expect **`schema_version`** in **`HAND.toml`** and warn when it is missing. AINL writes the same version family on **`HAND.toml`**, the IR file, and **`security.json`** so emitted packs validate cleanly.

**Source + tests:** `armaraos/emitter/armaraos.py` (`HAND_SCHEMA_VERSION`, `AINL_IR_SCHEMA_VERSION`), `tests/test_emit_armaraos_handpack.py`. **Operator guide:** [`../ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md) § *Emit a Hand package*.

## Where to see emitters in action

- Snapshot tests for emitted artifacts: `tests/test_snapshot_emitters.py`
- End-to-end API example using emitters: `examples/web/basic_web_api.ainl`

## Related sections

- Language definition: [`../language/README.md`](../language/README.md)
- Architecture and IR: [`../architecture/README.md`](../architecture/README.md)
- Example support framing: [`../examples/README.md`](../examples/README.md)
- Adapters (memory, vector_memory, tool_registry, code_context): [`../adapters/README.md`](../adapters/README.md)
