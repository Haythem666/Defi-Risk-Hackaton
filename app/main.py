"""Streamlit UI. Run from repo root: streamlit run app/main.py"""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from src.data import cache, morpho
from src.decision.exit_cost import exit_cost as position_exit_cost
from src.decision.rule import decide
from src.graph.build import build_graph
from src.risk.model import build_scenarios, simulate
from src.schemas import Position

COLORS = {"position": "#f4a261", "chain": "#8ecae6", "protocol": "#90be6d",
          "asset": "#ffd166", "issuer": "#f28482", "oracle": "#cdb4db",
          "market": "#a8dadc", "lending": "#b5838d", "venue": "#adb5bd", "vault": "#e9c46a",
          "admin": "#ffafcc"}

st.set_page_config(page_title="DeFi Risk Dependency", layout="wide")
st.title("DeFi Risk Dependency: stay or exit?")

# --- Inputs ---------------------------------------------------------------
with st.sidebar:
    st.header("Position (Morpho only)")
    kinds = {"Morpho Vault V2": "morpho_vault", "Lend in a Morpho market": "morpho_supply"}
    kind = kinds[st.radio("Pocket type", list(kinds))]
    chain_id = st.selectbox("Chain", list(morpho.NETWORKS), format_func=lambda c: morpho.CHAINS[c])
    if kind == "morpho_supply":
        labels = {f"{m['collateralAsset']['symbol']} / {m['loanAsset']['symbol']} "
                  f"({m['state']['supplyAssetsUsd'] / 1e6:,.0f}M)": m["marketId"]
                  for m in morpho.listed_markets(chain_id)}
        address = labels[st.selectbox("Morpho market (collateral / lent asset)", list(labels))]
    else:
        labels = {f"{v['name']} · {v['asset']['symbol']} ({(v['totalAssetsUsd'] or 0) / 1e6:,.0f}M)":
                  v["address"] for v in morpho.listed_vaults_v2(chain_id)}
        address = labels[st.selectbox("Morpho Vault V2 (largest listed)", list(labels))]
        typed = st.text_input("...or paste any Morpho Vault V2 address",
                              help="E.g. Belem RWA EURCV: 0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec").strip()
        address = typed or address
    size = st.number_input("Pocket size (USD)", 10_000, 500_000_000, 1_000_000, step=100_000)
    horizon = st.slider("Decision horizon (days)", 1, 365, 30)
    book_share = st.slider("Pocket share of the book", 0.01, 1.0, 0.10)

pos = Position(chain_id, address, float(size), horizon, book_share, kind)


@st.cache_data(ttl=600, show_spinner="Discovering dependencies from live data...")
def load_graph(p: Position):
    """The graph, and the log of every API call made to build it."""
    cache.CALLS.clear()
    g = build_graph(p)
    return g, list(cache.CALLS)


graph, api_calls = load_graph(pos)
by_id = {n.id: n for n in graph.nodes}

# --- 1. Dependency graph --------------------------------------------------
st.subheader("1. Dependency graph (from the Morpho API only)")
dot = ["digraph G { rankdir=LR; node [style=filled, shape=box, fontname=Helvetica];"]
for n in graph.nodes:
    dot.append(f'"{n.id}" [label="{n.name}\\n({n.type})", fillcolor="{COLORS[n.type]}"];')
for e in graph.edges:
    dot.append(f'"{e.source}" -> "{e.target}" [label="{e.kind} {e.exposure:.0%}", fontsize=9];')
dot.append("}")
st.graphviz_chart("\n".join(dot))

with st.expander("Edges and evidence"):
    st.dataframe(pd.DataFrame([vars(e) for e in graph.edges]), width="stretch")

with st.expander(f"API calls behind this graph ({len(api_calls)})"):
    apis = sorted({c["api"] for c in api_calls})
    shown = st.multiselect("APIs", apis, default=["morpho"] if "morpho" in apis else apis)
    st.caption("What each source was asked and the start of its answer; the whole answer is "
               "in the cache file. Same log in the terminal: python -m src.trace <kind> <chain> <address>")
    st.dataframe(pd.DataFrame([c for c in api_calls if c["api"] in shown]), width="stretch")

flags = [{"contract": n.name, "red flag": f} for n in graph.nodes for f in n.meta.get("flags") or []]
if flags:
    st.markdown("**Red flags** (vault settings that route deposits with no timelock)")
    st.dataframe(pd.DataFrame(flags), width="stretch")

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
use_brief = st.checkbox("Use the brief's reference exit cost (11%) instead of the liquidity check")
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
st.caption("Rates and severities: DATA rows are calibrated on DeFiLlama hacks and stablecoin history (data/calibration.json); JUDGEMENT rows are expert estimates.")
