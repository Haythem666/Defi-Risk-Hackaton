# DeFi Risk Dependency: EPFL Hackathon 2026 (Belem Capital challenge)

## Goal
Given a DeFi position (start: a Pendle PT), automatically:
1. discover its dependencies (chain, yield source/issuer, oracle, market/AMM, lending market),
2. estimate the economic loss if one of them is hit by an incident,
3. answer the risk manager's question: **STAY or EXIT**, and why.

Judging: dependency discovery 30%, impact estimation 30%, decision usefulness 25%,
working demo on REAL data 15%. It must run on real data, not just be slides.

## Decision rule (core idea)
Exit if `P(incident) * loss_if_hit > exit_cost + yield given up over the horizon` (the yield
you stop earning by holding cash instead), or when a lending position crosses its exit trigger u*.
Also report the breakeven probability `p* = exit_cost / loss_if_hit`.
The decision is taken now, before any incident: exit_cost is today's quote. Staying means leaving
late if an incident hits, with the crowd: each hit costing more than that late-exit cost is
increased by it (a PT sold with the PT lenders liquidate, capped where holding to maturity earns
30%/yr; a loan queues for idle liquidity, so no price cost, but only liquidity / deposits gets out
in a run).
Reference case from the brief: 10 pockets of 10%, one affected, unwinding costs 11% slippage.

## Stack
- Python 3.11+, Streamlit for the UI, networkx for the graph, numpy for Monte Carlo.
- Data: DeFiLlama API first, then Pendle API, then others as needed.
- Keep it simple. No extra frameworks, no premature abstraction.

## Structure
- `src/schemas.py`: shared data contract (Position, Node, Edge, DependencyGraph, Scenario, RiskResult, Verdict). Do not change silently.
- `src/data/`: fetchers for real data (one file per source): `pendle.py`, `defillama.py`, `morpho.py`,
  `aave.py`, `ethena.py` (where USDe backing sits), `hyperliquid.py` (perp vaults),
  `chain.py` (public RPC reads + Sourcify), `kyberswap.py` (DEX sell quotes), `kamino.py` (Solana
  lending: Earn vaults, markets, reserves),
  `coingecko.py` (a token's website, to find its issuer).
  All HTTP goes through `cache.fetch_json`, which saves every response to `data/cache/` (committed;
  bulky calibration inputs go to `data/raw/`, not committed)
  and falls back to it when the API is down. `DEFI_OFFLINE=1` forces cache only.
- `src/graph/`: builds a DependencyGraph for a position. `build.py` dispatches on `Position.kind`:
  `pendle_pt.py` (5 layers from live APIs), `lending.py` (Morpho market / Aave pool supply /
  Morpho vault), `perp_vault.py` (Hyperliquid vault: venue, bridge, oracle, positions),
  `kamino.py` (Kamino Earn vault or reserve on Solana: reserves, the market's collaterals weighted
  like an Aave pool, issuers, contagion; no oracle or program-authority reads on Solana).
  `common.py` holds shared helpers (chains, explorer links, issuer discovery, oracle checks,
  the feeds behind a Morpho oracle). `collateral.py` looks behind each lending collateral: issuer,
  bridge (Chainlink CCIP, LayerZero OFT) and home chain, who controls the token, other lenders
  accepting it, and whether liquidators can sell it (DEX exit).
- `src/risk/`: `calibration.py` (builds `data/calibration.json` from DeFiLlama hacks, protocol TVL
  history and stablecoin prices: `python -m src.risk.calibration`), `assumptions.py` (picks the rate
  and severity for each node: DATA rows from the calibration, JUDGEMENT rows labelled as such),
  `model.py` (scenarios, propagation, Poisson horizon probability, Monte Carlo -> RiskResult),
  `stress.py` (stress engine: each node hit at 5/20/50/100%, losses spread by capped DebtRank
  fixed-point propagation; value edges add up, shared dependencies count once (max); a lender loses
  only beyond the LLTV buffer, recovering the collateral at its DEX exit price; liquidation-spiral
  loop gain g per collateral, stalled when liquidations do not pay; spectral radius of the exposure
  matrix with spiral gains on the diagonal). Scenario losses come from this engine.
- `src/decision/`: `exit_cost.py` (live Pendle router quote; pool liquidity for loans; `late_exit`: leaving
  after an incident, with the crowd) + `rule.py` (STAY/EXIT -> Verdict; `with_late_exit`)
  + `snell.py` (optimal-stopping exit trigger for lending positions: exit when utilization > u* =
  1 - (KAPPA (H - C) / r)^(1/GAMMA), H = stress-engine haircut if trapped; KAPPA/GAMMA JUDGEMENT,
  anchored on a 0.2/yr freeze hazard at the 90% target utilization).
- `app/`: Streamlit app (`streamlit run app/main.py`), one pocket at a time.
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
  A market's exposure to its collateral's DEX exit = utilization x (price impact of selling what a
  5% drop liquidates, KyberSwap quote) / liquidation bonus, capped at utilization.
  Exposure along the graph = sum over paths of the product of edge exposures, capped at 1.
- Real: graph discovery (Pendle + DeFiLlama + Morpho + Aave), issuer found automatically from
  DeFiLlama yield pools (the largest pool of the token, if it mints it rather than lends it), oracle price read on-chain and compared
  to the PT market price, oracle source verification (Sourcify), exit cost (Pendle router quote).
- Calibrated (data/calibration.json, last 3y of hacks on protocols holding >= 100M USD; depegs since
  2021): hack rate and severity per DeFiLlama category (pulled toward all-DeFi when data is thin),
  oracle manipulation, large-exchange hacks, stablecoin depegs per family blended with each coin's
  own record. Still JUDGEMENT: chain halt, Pendle pool liquidity crunch, lending cascade, LST depeg,
  collateral DEX exit drying up.
- Collateral depth (Morpho markets and Aave pools): issuer from DeFiLlama yield pools, else the
  token's CoinGecko website matched to a DeFiLlama protocol (PST -> Huma); bridged copies found
  on-chain (PST: CCIP burn/mint pool, backed on Solana); token controllers; oracle feeds with a flag
  when the price is a reported rate, not a market price; DEX exit vs the liquidation bonus (a PT is
  quoted on its Pendle pool; a collateral no DEX trades is flagged whatever the drop, exposure =
  utilization). Collateral that wraps another token is opened, 2 levels deep: a PT via the Pendle
  API (PT-reUSD -> reUSD), a vault share via ERC-4626 asset() (siUSD -> iUSD; a Morpho vault share
  also brings its markets). An issuer whose DeFiLlama category means off-chain assets (RWA, RWA
  Lending, Basis Trading, CeDeFi, Off-Chain Credit) gets an "Off-chain backing" box: where the graph stops.
- Contagion: other lending protocols (DeFiLlama category Lending/CDP) holding the same collateral,
  here and where it is bridged from, are nodes; exposure = 5% of their holding liquidated over the
  token's DEX liquidity (1 if it has no market); markets already in the graph are subtracted.
- Issuer depth: Ethena -> exchange venues (Binance, OKX, ...) from Ethena's transparency API,
  exposure = venue share of backing. Protocol/issuer nodes carry DeFiLlama category, audits and
  past hacks (input for calibrating the risk model).
- Known gaps: Kamino oracles and Solana program authorities not read; Euler not covered (no keyless API), venues only for Ethena, Aave PT exposure still crude (share of PT TVL), late exit ignores LPs
  pulling Pendle liquidity in a crisis, no portfolio view (one pocket at a time).

## Commands
- Install: `pip install -r requirements.txt`
- Run app: `streamlit run app/main.py`
- Tests: `pytest` (the graph test runs offline on `data/cache/`)
- Offline demo: `DEFI_OFFLINE=1 streamlit run app/main.py`
- See every API call behind a graph (what was asked, live or cache, the answer):
  `python -m src.trace morpho_vault 1 <vault address> --api morpho [--full]`; same log in the app
  (expander "API calls behind this graph") and on the `defi.api` logger.
