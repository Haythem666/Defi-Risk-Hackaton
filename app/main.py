"""Streamlit UI. Run from repo root: streamlit run app/main.py"""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from src.data import aave, morpho, pendle
from src.decision.exit_cost import exit_cost as position_exit_cost
from src.decision.rule import decide
from src.graph.build import build_graph
from src.graph.common import CHAINS
from src.risk.model import build_scenarios, simulate
from src.schemas import Position

COLORS = {"position": "#f4a261", "chain": "#8ecae6", "protocol": "#90be6d",
          "asset": "#ffd166", "issuer": "#f28482", "oracle": "#cdb4db",
          "market": "#a8dadc", "lending": "#b5838d", "venue": "#adb5bd", "vault": "#e9c46a"}

st.set_page_config(page_title="DeFi Risk Dependency", layout="wide")
st.title("DeFi Risk Dependency: stay or exit?")

# --- Inputs ---------------------------------------------------------------
with st.sidebar:
    st.header("Position")
    kinds = {"Pendle PT": "pendle_pt", "Lend on Morpho": "morpho_supply",
             "Supply to Aave": "aave_supply", "Morpho vault": "morpho_vault"}
    kind = kinds[st.radio("Pocket type", list(kinds))]
    # Only offer chains where this pocket type exists.
    supported = {"pendle_pt": list(CHAINS), "morpho_supply": list(morpho.NETWORKS),
                 "aave_supply": list(aave.CHAIN_IDS), "morpho_vault": list(morpho.NETWORKS)}[kind]
    chain_id = st.selectbox("Chain", supported, format_func=lambda c: CHAINS[c])
    asset_address = None
    if kind == "pendle_pt":
        markets = sorted(pendle.active_markets(chain_id), key=lambda m: m["name"])
        labels = {f"{m['name']} ({m['expiry'][:10]})": m["address"] for m in markets}
        default = next((i for i, k in enumerate(labels) if k.startswith("sUSDe (")), 0)
        address = labels[st.selectbox("Pendle PT market", list(labels), index=default)]
    elif kind == "morpho_supply":
        labels = {f"{m['collateralAsset']['symbol']} / {m['loanAsset']['symbol']} "
                  f"({m['state']['supplyAssetsUsd'] / 1e6:,.0f}M)": m["marketId"]
                  for m in morpho.listed_markets(chain_id)}
        address = labels[st.selectbox("Morpho market (collateral / lent asset)", list(labels))]
    elif kind == "morpho_vault":
        labels = {f"{v['name']} · {v['asset']['symbol']} ({v['state']['totalAssetsUsd'] / 1e6:,.0f}M)":
                  v["address"] for v in morpho.listed_vaults(chain_id)}
        address = labels[st.selectbox("Morpho vault", list(labels))]
    else:
        pools = {m["name"]: m for m in aave.markets(chain_id)}
        pool = pools[st.selectbox("Aave pool", list(pools))]
        address = pool["address"]
        reserves = sorted(pool["reserves"], key=lambda r: -float(r["size"]["usd"] or 0))
        labels = {f"{r['underlyingToken']['symbol']} ({float(r['size']['usd']) / 1e6:,.0f}M)":
                  r["underlyingToken"]["address"] for r in reserves if float(r["size"]["usd"] or 0) >= 1e6}
        asset_address = labels[st.selectbox("Asset supplied", list(labels))]
    size = st.number_input("Pocket size (USD)", 10_000, 500_000_000, 1_000_000, step=100_000)
    horizon = st.slider("Decision horizon (days)", 1, 365, 30)
    book_share = st.slider("Pocket share of the book", 0.01, 1.0, 0.10)

pos = Position(chain_id, address, float(size), horizon, book_share, kind, asset_address)


@st.cache_data(ttl=600, show_spinner="Discovering dependencies from live data...")
def load_graph(p: Position):
    return build_graph(p)


graph = load_graph(pos)
by_id = {n.id: n for n in graph.nodes}

# --- 1. Dependency graph --------------------------------------------------
st.subheader("1. Dependency graph (discovered from live data)")
dot = ["digraph G { rankdir=LR; node [style=filled, shape=box, fontname=Helvetica];"]
for n in graph.nodes:
    dot.append(f'"{n.id}" [label="{n.name}\\n({n.type})", fillcolor="{COLORS[n.type]}"];')
for e in graph.edges:
    dot.append(f'"{e.source}" -> "{e.target}" [label="{e.kind} {e.exposure:.0%}", fontsize=9];')
dot.append("}")
st.graphviz_chart("\n".join(dot))

with st.expander("Edges and evidence"):
    st.dataframe(pd.DataFrame([vars(e) for e in graph.edges]), width="stretch")

oracles = [n for n in graph.nodes if n.type == "oracle"]
if oracles:
    st.markdown("**Oracle checks** (price vs PT market price, public source code)")
    st.dataframe(pd.DataFrame([{
        "oracle": n.meta["address"],
        "price (USD)": f"{n.meta['price_usd']:.4f}" if n.meta.get("price_usd") else "-",
        "gap to market": f"{n.meta['gap_to_market']:+.2%}" if n.meta.get("gap_to_market") is not None else "-",
        "source verified": "yes" if n.meta.get("source_verified") else "NO",
        "proxy of": n.meta.get("proxy_of") or "-",
        "read from": n.meta.get("source")} for n in oracles]), width="stretch")

# --- 2. Risk --------------------------------------------------------------
st.subheader("2. Incident scenarios over the horizon")
scenarios = build_scenarios(graph, horizon)

stress_node = st.selectbox(
    "Stress test: suppose this dependency is hit right now",
    ["(none)"] + sorted({s.node_id for s in scenarios}))
if stress_node != "(none)":
    p_stress = st.slider("Probability the incident turns into a loss for us", 0.0, 1.0, 0.5)
    scenarios = [replace(s, probability=p_stress) if s.node_id == stress_node else s
                 for s in scenarios]

risk = simulate(scenarios)
st.dataframe(pd.DataFrame([{
    "node": by_id[s.node_id].name, "incident": s.incident,
    "probability": f"{s.probability:.2%}", "loss if hit": f"{s.loss_if_hit:.1%}",
    "expected": f"{s.probability * s.loss_if_hit:.3%}", "rationale": s.rationale}
    for s in scenarios]), width="stretch")

# --- 3. Decision ----------------------------------------------------------
st.subheader("3. Decision")
est_cost, cost_source = position_exit_cost(pos, graph)
use_brief = st.checkbox("Use the brief's reference exit cost (11%) instead of the live quote")
exit_cost = 0.11 if use_brief else est_cost
verdict = decide(risk, exit_cost)

c = st.columns(5)
c[0].metric("Verdict", verdict.decision)
c[1].metric("Expected loss", f"{risk.expected_loss:.2%}",
            help=f"= {risk.expected_loss * size:,.0f} USD, {risk.expected_loss * book_share:.3%} of book")
c[2].metric("Worst 5% loss", f"{risk.worst_case_loss:.2%}")
c[3].metric("Exit cost", f"{exit_cost:.2%}",
            help="Brief reference case" if use_brief else cost_source)
c[4].metric("Breakeven p*", "-" if verdict.breakeven_probability is None
            else f"{verdict.breakeven_probability:.1%}",
            help="If the worst scenario's probability is above this, exiting is cheaper.")
(st.error if verdict.decision == "EXIT" else st.success)(verdict.reason)
if "stuck" in cost_source:
    st.warning(cost_source)
st.caption("Phase 0: incident probabilities and severities are placeholders (see src/risk/assumptions.py).")
