# DeFi Risk Dependency: stay or exit?

EPFL Hackathon 2026, Belem Capital challenge. Given a DeFi position, the app
discovers its dependencies from live on-chain data, estimates the loss if one
of them is hit, and answers the risk manager's question: **STAY or EXIT**.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app/main.py        # opens http://localhost:8501
pytest                           # tests
```

No API keys needed. Data sources: [Pendle API](https://api-v2.pendle.finance/core/docs),
[DeFiLlama](https://defillama.com/docs/api), [Morpho API](https://docs.morpho.org/tools/offchain/api/).
Every response is cached in `data/cache/`; run with `DEFI_OFFLINE=1` to use the cache only.

## How it works

1. **Discovery** (`src/graph/`): from a Pendle market address, build the 5-layer
   graph: chain, yield source + issuer, oracle, PT market (AMM), lending markets
   that accept the PT as collateral. Every edge carries its evidence (URL).
2. **Impact** (`src/risk/`): each node gets incident scenarios (hack, depeg, ...).
   Loss on the position = severity x exposure along the graph. Monte Carlo gives
   the expected loss and the worst-5% loss over the decision horizon.
3. **Decision** (`src/decision/`): exit cost comes from a live Pendle router quote.
   EXIT if expected loss > exit cost. Breakeven probability `p* = exit_cost / loss_if_hit`.

See `CLAUDE.md` for the team rules and `CONTEXT.md` for the plan.
