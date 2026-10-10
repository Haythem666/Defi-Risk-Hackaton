# DeFi Risk Dependency: EPFL Hackathon 2026 (Belem Capital challenge)

> **Branch `claude/morpho-only`: a learning version.** Only the Morpho API is used (no
> DeFiLlama, no on-chain reads, no other protocol). Two positions: a Morpho Vault V2 (Belem's
> vaults are all V2; older v1 vaults are not covered here) and lending in a Morpho market. Code: `src/data/morpho.py` (the queries),
> `src/graph/morpho.py` (answers -> nodes and edges), then the same risk model and decision.
> See every call: `python -m src.trace morpho_vault 1 <vault address> --full`.
> The full version lives on `claude/hackaton-prep-hk0zf3`.

## Goal
Given a DeFi position (start: a Pendle PT), automatically:
1. discover its dependencies (chain, yield source/issuer, oracle, market/AMM, lending market),
2. estimate the economic loss if one of them is hit by an incident,
3. answer the risk manager's question: **STAY or EXIT**, and why.

Judging: dependency discovery 30%, impact estimation 30%, decision usefulness 25%,
working demo on REAL data 15%. It must run on real data, not just be slides.

## Decision rule (core idea)
Exit if `P(incident) * loss_if_hit > exit_cost`.
Also report the breakeven probability `p* = exit_cost / loss_if_hit`.
Reference case from the brief: 10 pockets of 10%, one affected, unwinding costs 11% slippage.

## Stack
- Python 3.11+, Streamlit for the UI, networkx for the graph, numpy for Monte Carlo.
- Data: DeFiLlama API first, then Pendle API, then others as needed.
- Keep it simple. No extra frameworks, no premature abstraction.

## Structure
- `src/schemas.py`: shared data contract (Position, Node, Edge, DependencyGraph, Scenario, RiskResult, Verdict). Do not change silently.
- `src/data/`: fetchers for real data (one file per source): `pendle.py`, `defillama.py`, `morpho.py`,
  `aave.py`, `ethena.py` (where USDe backing sits), `hyperliquid.py` (perp vaults),
  `chain.py` (public RPC reads + Sourcify).
  All HTTP goes through `cache.fetch_json`, which saves every response to `data/cache/` (committed;
  bulky calibration inputs go to `data/raw/`, not committed)
  and falls back to it when the API is down. `DEFI_OFFLINE=1` forces cache only.
- `src/graph/`: builds a DependencyGraph for a position. `build.py` dispatches on `Position.kind`:
  `pendle_pt.py` (5 layers from live APIs), `lending.py` (Morpho market / Aave pool supply /
  Morpho vault), `perp_vault.py` (Hyperliquid vault: venue, bridge, oracle, positions).
  `common.py` holds shared helpers (chains, explorer links, issuer discovery, oracle checks).
- `src/risk/`: `calibration.py` (builds `data/calibration.json` from DeFiLlama hacks, protocol TVL
  history and stablecoin prices: `python -m src.risk.calibration`), `assumptions.py` (picks the rate
  and severity for each node: DATA rows from the calibration, JUDGEMENT rows labelled as such),
  `model.py` (scenarios, propagation, Poisson horizon probability, Monte Carlo -> RiskResult).
- `src/decision/`: `exit_cost.py` (live Pendle router quote; pool liquidity for loans) + `rule.py` (STAY/EXIT -> Verdict).
- `app/`: Streamlit app (`streamlit run app/main.py`).
- `data/examples/`: hand-made example graphs and past incidents.
- `tests/`: pytest.

## Rules
- Every dependency edge should carry an `evidence` (URL or note). No invented edges.
- Every risk number should carry a `rationale` (where it comes from). Numbers must be defensible.
- Real data with cached snapshots (the demo must survive an API outage).
- Work on your own module and own files. Talk before touching someone else's.
- Small commits, push at least once a day, `main` must always run.
- Plan first for anything non-trivial, then code. Prefer Sonnet; use Opus only for hard problems.

## Current status
- End-to-end slice works on six chains (Ethereum, Arbitrum, Base, BSC, HyperEVM, Plasma; each
  protocol only where its API covers the chain) for five pocket types: any live Pendle PT (reference:
  PT-sUSDe 26NOV2026, `0x47ad2cd1dd15739a7a035b9d3b7828d916fef77e`), lending in a listed Morpho
  market, supplying to an Aave v3 pool, depositing in a Morpho vault (v1, or Vault V2 via its adapters,
  e.g. Belem RWA EURCV `0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec`; owner/curator classified on-chain,
  per-setting timelocks with a flag when routing changes have none), and depositing in a
  Hyperliquid vault that trades perps (the brief's "vault deploying into an external venue"). A lender's exposure
  to collateral = pool utilization; a vault's exposure to a market = its share of the vault.
  A PT's exposure to a Morpho market = PT liquidated if its price drops 5% (Morpho
  marketCollateralAtRisk) / Pendle pool liquidity, capped at 1 (forced-selling pressure).
  Exposure along the graph = sum over paths of the product of edge exposures, capped at 1.
- Real: graph discovery (Pendle + DeFiLlama + Morpho + Aave), issuer found automatically from
  DeFiLlama yield pools (the largest pool of the token, if it mints it rather than lends it), oracle price read on-chain and compared
  to the PT market price, oracle source verification (Sourcify), exit cost (Pendle router quote).
- Calibrated (data/calibration.json, last 3y of hacks on protocols holding >= 100M USD; depegs since
  2021): hack rate and severity per DeFiLlama category (pulled toward all-DeFi when data is thin),
  oracle manipulation, large-exchange hacks, stablecoin depegs per family blended with each coin's
  own record. Still JUDGEMENT: chain halt, Pendle pool liquidity crunch, lending cascade, LST depeg.
- Issuer depth: Ethena -> exchange venues (Binance, OKX, ...) from Ethena's transparency API,
  exposure = venue share of backing. Protocol/issuer nodes carry DeFiLlama category, audits and
  past hacks (input for calibrating the risk model).
- Known gaps: Euler not covered (no keyless API), venues only for Ethena, Aave PT exposure still crude (share of PT TVL), exit cost ignores forgone yield and crisis
  liquidity, no portfolio view yet.

## Commands
- Install: `pip install -r requirements.txt`
- Run app: `streamlit run app/main.py`
- Tests: `pytest` (the graph test runs offline on `data/cache/`)
- Offline demo: `DEFI_OFFLINE=1 streamlit run app/main.py`
- See every API call behind a graph (what was asked, live or cache, the answer):
  `python -m src.trace morpho_vault 1 <vault address> --api morpho [--full]`; same log in the app
  (expander "API calls behind this graph") and on the `defi.api` logger.
