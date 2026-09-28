# Context handoff (from the planning chat on claude.ai)

## Challenge
Belem Capital "DeFi Risk Dependency Challenge" (EPFL Hackathon 2026). Build a system that
takes a DeFi position, discovers its dependencies, estimates the loss if one is hit, and
answers: STAY or EXIT? Must run on real data. Judging: dependency discovery 30%,
impact estimation 30%, decision usefulness 25%, working demo on real data 15%.
Mentors from Belem are available during the event (ask them for reference positions,
which incident types matter, decision horizon).

## Team
5 people, all on Claude Pro. Rules on pre-coding: allowed by the hackathon rules.

## Decisions made
- Start with ONE position: the Pendle PT example from the brief (5 layers: settlement chain,
  yield source + issuer, oracle, PT market/AMM, lending market using it as collateral).
  Then add 2 more types: a lending-market position and a vault routing to an external venue (perp).
- Stack: Python + Streamlit + networkx + numpy.
- Core decision idea: exit if P(incident) x loss_if_hit > exit_cost; also show the breakeven
  probability p* = exit_cost / loss_if_hit. Reference case: 10 pockets of 10%, one affected,
  unwinding costs 11% slippage.
- Uncertainty handled with Monte Carlo + sensitivity analysis (show how the verdict moves when
  assumptions change). Validate on past incidents (e.g. Euler 2023, Curve/Vyper 2023, Terra depeg).

## Roles (5 people)
1. Data (DeFiLlama, Pendle API, cached snapshots)
2. Dependency graph (build the 5-layer graph for the Pendle PT)
3. Risk model (scenarios, propagation, Monte Carlo)
4. Decision + exit cost (STAY/EXIT rule, slippage from market depth / AMM curve)
5. UI + demo + list of past incidents

## Plan
- Phase 0 (now): repo, CLAUDE.md, shared schemas (src/schemas.py), one tiny working piece each.
- Phase 1: end-to-end vertical slice on the Pendle PT (fake numbers OK).
- Phase 2: real data, deeper discovery, defensible impact numbers, validation on past incidents.
- Phase 3: decision screen + portfolio view (10 pockets).
- Phase 4: freeze features, cached data, demo script, backup video, pitch.
- Daily: everyone pushes; main must always run; 15-min sync.

## Open questions
- Exact data sources per protocol and their API limits.
- Which incident probabilities to use and how to justify them.
