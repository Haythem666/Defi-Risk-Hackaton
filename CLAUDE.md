# DeFi Risk Dependency: EPFL Hackathon 2026 (Belem Capital challenge)

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
- `src/data/`: fetchers for real data (one file per source): `pendle.py`, `defillama.py`, `morpho.py`.
  All HTTP goes through `cache.fetch_json`, which saves every response to `data/cache/` (committed)
  and falls back to it when the API is down. `DEFI_OFFLINE=1` forces cache only.
- `src/graph/`: builds a DependencyGraph for a position (`pendle_pt.py`: 5 layers from live APIs).
- `src/risk/`: `assumptions.py` (incident rates, PLACEHOLDERS to calibrate), `model.py` (scenarios, propagation, Monte Carlo -> RiskResult).
- `src/decision/`: `exit_cost.py` (live Pendle router quote) + `rule.py` (STAY/EXIT -> Verdict).
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

## Current status (Phase 0 done)
- End-to-end slice works on the live PT-sUSDe 26NOV2026 market (Ethereum, `0x47ad2cd1dd15739a7a035b9d3b7828d916fef77e`).
- Real: graph discovery (Pendle + DeFiLlama + Morpho), liquidity, exit cost (Pendle router quote).
- Fake: incident probabilities and severities in `src/risk/assumptions.py`.
- Known gaps: oracle type is "Unknown" (read on-chain feed), only Morpho lending (add Aave/Euler),
  exposure of lending edges is crude, exit cost ignores forgone fixed yield, no portfolio view yet.

## Commands
- Install: `pip install -r requirements.txt`
- Run app: `streamlit run app/main.py`
- Tests: `pytest` (the graph test runs offline on `data/cache/`)
- Offline demo: `DEFI_OFFLINE=1 streamlit run app/main.py`
