"""Streamlit UI. Run from repo root: streamlit run app/main.py"""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from src.data import aave, cache, hyperliquid, morpho, pendle
from src.decision.exit_cost import exit_cost as position_exit_cost
from src.decision.rule import decide
from src.graph.build import build_graph
from src.graph.common import CHAINS
from src.risk.model import build_scenarios, simulate
from src.schemas import Position

COLORS = {"position": "#f4a261", "chain": "#8ecae6", "protocol": "#90be6d",
          "asset": "#ffd166", "issuer": "#f28482", "oracle": "#cdb4db",
          "market": "#a8dadc", "lending": "#b5838d", "venue": "#adb5bd", "vault": "#e9c46a",
          "admin": "#ffafcc"}

NODE_DESCRIPTIONS = {
    "position": ("Orange", "Position", "The investment you hold and are assessing."),
    "chain": ("Blue", "Blockchain", "The network that executes and settles transactions."),
    "protocol": ("Green", "Protocol", "The smart-contract system providing the DeFi service."),
    "asset": ("Yellow", "Asset", "A token underlying, denominating, or securing the investment."),
    "issuer": ("Coral", "Issuer", "The project or entity issuing the underlying token."),
    "oracle": ("Lavender", "Price oracle", "The price feed used to value assets or collateral."),
    "market": ("Teal", "Trading market", "The trading pool used to sell or exchange an asset."),
    "lending": ("Mauve", "Lending market", "A market where assets are lent against collateral."),
    "venue": ("Gray", "External venue", "An exchange or platform used for hedging or trading."),
    "vault": ("Gold", "Vault", "A strategy that manages deposits and allocates them to markets."),
    "admin": ("Pink", "Administrator", "An address with control permissions, such as changing settings or upgrading contracts."),
}

st.set_page_config(page_title="DeFi Risk Dependency", layout="wide")
st.title("DeFi Risk Dependency: stay or exit?")

# --- Inputs ---------------------------------------------------------------
with st.sidebar:
    st.header("Position")
    kinds = {"Pendle PT": "pendle_pt", "Lend on Morpho": "morpho_supply",
             "Supply to Aave": "aave_supply", "Morpho vault": "morpho_vault",
             "Hyperliquid vault (perps)": "hyperliquid_vault",
             "Any contract (on-chain crawler)": "contract"}
    kind = kinds[st.radio("Pocket type", list(kinds))]
    # Only offer chains where this pocket type exists.
    supported = {"pendle_pt": list(CHAINS), "morpho_supply": list(morpho.NETWORKS),
                 "aave_supply": list(aave.CHAIN_IDS), "morpho_vault": list(morpho.NETWORKS),
                 "hyperliquid_vault": [999], "contract": list(CHAINS)}[kind]
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
        vaults = [(v["name"], v["asset"]["symbol"], v["state"]["totalAssetsUsd"] or 0, v["address"], "")
                  for v in morpho.listed_vaults(chain_id)]
        vaults += [(v["name"], v["asset"]["symbol"], v["totalAssetsUsd"] or 0, v["address"], " · V2")
                   for v in morpho.listed_vaults_v2(chain_id)]
        labels = {f"{n} · {s} ({t / 1e6:,.0f}M){ver}": a
                  for n, s, t, a, ver in sorted(vaults, key=lambda x: -x[2])}
        address = labels[st.selectbox("Morpho vault (v1 and V2, largest listed)", list(labels))]
        typed = st.text_input("...or paste any Morpho vault address (v1 or V2)",
                              help="E.g. Belem RWA EURCV: 0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec").strip()
        address = typed or address
    elif kind == "contract":
        address = st.text_input(
            "Token or vault address", "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497" if chain_id == 1 else "",
            help="Dependencies are read from the contracts themselves (default: sUSDe). "
                 "Try the Steakhouse USDC vault: 0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB").strip()
        if not address:
            st.stop()
    elif kind == "hyperliquid_vault":
        address = st.text_input("Hyperliquid vault address", hyperliquid.HLP,
                                help="Default: HLP, the exchange's market-making vault").strip()
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
    """The graph, and the log of every API call made to build it."""
    cache.CALLS.clear()
    g = build_graph(p)
    return g, list(cache.CALLS)


graph, api_calls = load_graph(pos)
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

st.markdown("**Box colors — what each component represents**")
st.caption("Colors identify component types, not risk levels. Each box also shows its type in parentheses.")
present_types = {n.type for n in graph.nodes}
legend_items = []
for node_type, (color_name, label, description) in NODE_DESCRIPTIONS.items():
    if node_type in present_types:
        legend_items.append(
            '<div style="display:flex;align-items:flex-start;gap:10px;">'
            f'<span aria-hidden="true" style="background:{COLORS[node_type]};'
            'width:18px;height:18px;flex:0 0 18px;border:1px solid #555;'
            'border-radius:3px;margin-top:3px;"></span>'
            f'<div><strong>{color_name} — {label}</strong><br>{description}</div></div>'
        )
st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));'
    'gap:14px 24px;margin-bottom:18px;">' + "".join(legend_items) + "</div>",
    unsafe_allow_html=True,
)

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
    st.markdown("**Red flags** (read on-chain: who controls each contract, upgradeability, "
                "withdrawal delays, unpublished code)")
    st.dataframe(pd.DataFrame(flags), width="stretch")

oracles = [n for n in graph.nodes if n.type == "oracle"]
if oracles:
    st.markdown("**Oracle checks** (price vs PT market price, public source code)")
    st.dataframe(pd.DataFrame([{
        "oracle": n.meta.get("address") or n.name,
        "price (USD)": f"{n.meta['price_usd']:.4f}" if n.meta.get("price_usd") else "-",
        "gap to market": f"{n.meta['gap_to_market']:+.2%}" if n.meta.get("gap_to_market") is not None else "-",
        "source verified": {True: "yes", False: "NO"}.get(n.meta.get("source_verified", n.meta.get("verified")), "n/a"),
        "proxy of": n.meta.get("proxy_of") or n.meta.get("implementation") or "-",
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
st.caption("Rates and severities: DATA rows are calibrated on DeFiLlama hacks and stablecoin history (data/calibration.json); JUDGEMENT rows are expert estimates.")
