"""Whole-book view: several pockets judged together (src/decision/book.py)."""

import altair as alt
import pandas as pd
import streamlit as st

from src.decision import book
from src.graph.common import CHAINS
from src.schemas import Position

KINDS = {"Pendle PT": "pendle_pt", "Morpho vault": "morpho_vault", "Lend on Morpho": "morpho_supply",
         "Kamino vault or reserve": "kamino", "Hyperliquid vault": "hyperliquid_vault",
         "Any contract": "contract"}
KIND_LABEL = {v: k for k, v in KINDS.items()}
CHAIN_BY_NAME = {v: k for k, v in CHAINS.items()}

# A Belem-like book: the pockets the demo uses, 1M USD each.
DEMO_BOOK = [
    ("PT-sUSDe 26NOV2026", "Pendle PT", "Ethereum", "0x47ad2cd1dd15739a7a035b9d3b7828d916fef77e"),
    ("RockawayX USDC Yield", "Morpho vault", "Ethereum", "0xE0181090c22579B6A217f1522cbf8c9f1F0C1965"),
    ("Huma USDC Main", "Morpho vault", "Ethereum", "0x8aC91877b93330f52b2979a31a4879506021475c"),
    ("Belem RWA EURCV", "Morpho vault", "Ethereum", "0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec"),
    ("Kamino Steakhouse HY USDC", "Kamino vault or reserve", "Solana", "BEEfo7xwgK2ZP13Pxo7qqTPzAteKJmXjVWtMWcXSvbn2"),
    ("Kamino RWA USDC", "Kamino vault or reserve", "Solana", "DWSXb18xZApz29vnQpgR2m6MynCT7PznaXt7Ut7M7KaP"),
]

# Status colors (STAY good / EXIT critical), always shown with an icon and a word.
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
BAR = "#2a78d6"
TYPE_COLORS = {"chain": "#8ecae6", "protocol": "#90be6d", "asset": "#ffd166", "issuer": "#f28482",
               "oracle": "#cdb4db", "market": "#a8dadc", "lending": "#b5838d", "venue": "#adb5bd",
               "vault": "#e9c46a", "admin": "#ffafcc"}

CSS = """
<style>
.bk-hero{border-radius:14px;padding:22px 26px;margin:4px 0 18px;
  background:linear-gradient(120deg,rgba(42,120,214,.14),rgba(42,120,214,.03));
  border:1px solid rgba(42,120,214,.25)}
.bk-hero h2{margin:0;font-size:1.9rem;line-height:1.2}
.bk-hero p{margin:6px 0 0;opacity:.75}
.bk-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:22px}
.bk-kpi{border:1px solid rgba(128,128,128,.25);border-radius:12px;padding:14px 16px}
.bk-kpi .l{font-size:.8rem;opacity:.7;text-transform:uppercase;letter-spacing:.04em}
.bk-kpi .v{font-size:1.6rem;font-weight:700;margin-top:2px}
.bk-kpi .s{font-size:.85rem;opacity:.75}
.bk-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:10px}
.bk-card{border:1px solid rgba(128,128,128,.25);border-left:6px solid var(--c);border-radius:12px;
  padding:14px 16px}
.bk-card .top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.bk-card .name{font-weight:700;font-size:1.02rem}
.bk-card .meta{font-size:.82rem;opacity:.7;margin:2px 0 10px}
.bk-pill{font-weight:700;font-size:.8rem;padding:3px 10px;border-radius:999px;color:#fff;
  background:var(--c);white-space:nowrap}
.bk-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px}
.bk-grid .l{font-size:.72rem;opacity:.65;text-transform:uppercase;letter-spacing:.03em}
.bk-grid .v{font-weight:600}
.bk-why{font-size:.83rem;opacity:.85;border-top:1px dashed rgba(128,128,128,.35);padding-top:8px}
.bk-bar{height:6px;border-radius:3px;background:rgba(128,128,128,.2);margin:4px 0 10px;overflow:hidden}
.bk-bar>div{height:100%;background:#2a78d6;border-radius:3px}
</style>
"""


def _usd(x: float) -> str:
    return f"{x / 1e6:,.2f}M USD" if abs(x) >= 1e6 else f"{x:,.0f} USD"


@st.cache_data(ttl=600, show_spinner=False)
def _evaluate(p: Position) -> dict:
    return book.evaluate(p)


def _short_reason(r: dict) -> str:
    v, rule, late = r["verdict"], r["rule"], r["late"]
    if rule and rule["triggered"]:
        return (f"Markets {rule['utilization']:.1%} borrowed, above its exit trigger "
                f"{rule['u_star']:.1%}: leave before withdrawals freeze.")
    cost = r["exit_cost"] + r["forgone"]
    word = "above" if v.decision == "EXIT" else "below"
    txt = f"Expected loss {r['risk'].expected_loss:.2%} is {word} the {cost:.2%} it costs to leave."
    if late and late.get("crowd_usd") and r["pos"].kind == "pendle_pt":
        txt += f" Leaving late, with the crowd, would cost {late['cost']:.2%}."
    return txt


def _action(r: dict) -> str:
    p, v, late = r["pos"], r["verdict"], r["late"] or {}
    if v.decision == "STAY":
        return "Hold"
    if p.kind == "pendle_pt":
        return f"Sell the PT on Pendle now ({_usd(p.size_usd * r['exit_cost'])} slippage)"
    now = late.get("withdrawable_now")
    if now is not None and now < 1:
        return (f"Withdraw {_usd(p.size_usd * now)} now; {_usd(p.size_usd * (1 - now))} "
                f"waits for borrowers to repay")
    return f"Withdraw all {_usd(p.size_usd)} now (no slippage)"


def render(horizon: int) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("Several pockets judged together. Each one gets the same pipeline as the pocket "
                "view; the book adds **what they share**: one failure of a shared dependency hits "
                "every pocket that relies on it at once.")

    with st.expander("Your book: edit the pockets (add a row, paste an address)", expanded=False):
        base = pd.DataFrame(DEMO_BOOK, columns=["Pocket", "Type", "Chain", "Address"])
        base["Size (USD)"] = 1_000_000
        edited = st.data_editor(
            base, num_rows="dynamic", width="stretch", hide_index=True,
            column_config={
                "Type": st.column_config.SelectboxColumn(options=list(KINDS), required=True),
                "Chain": st.column_config.SelectboxColumn(options=list(CHAIN_BY_NAME), required=True),
                "Size (USD)": st.column_config.NumberColumn(min_value=10_000, step=100_000, format="%d"),
            })
    rows = [r for r in edited.to_dict("records") if r.get("Address") and r.get("Type") and r.get("Chain")]
    if not rows:
        st.info("Add at least one pocket.")
        return
    total = sum(float(r["Size (USD)"] or 0) for r in rows)

    pockets, failed = [], []
    bar = st.progress(0.0, "Discovering each pocket's dependencies from live data...")
    for i, r in enumerate(rows):
        pos = Position(CHAIN_BY_NAME[r["Chain"]], str(r["Address"]).strip(), float(r["Size (USD)"]),
                       horizon, float(r["Size (USD)"]) / total, KINDS[r["Type"]])
        try:
            res = _evaluate(pos)
            res["label"] = r["Pocket"] or f"Pocket {i + 1}"
            pockets.append(res)
        except Exception as e:  # one bad address must not take the book down
            failed.append(f"{r['Pocket']}: {type(e).__name__} {e}")
        bar.progress((i + 1) / len(rows), f"{r['Pocket']} done")
    bar.empty()
    for f in failed:
        st.warning(f"Skipped {f}")
    if not pockets:
        return
    total = sum(p["pos"].size_usd for p in pockets)

    # --- Headline ------------------------------------------------------------
    joint = book.simulate_book(pockets)
    alone = book.simulate_book(pockets, shared=False)
    shared = book.shared_dependencies(pockets)
    exits = [p for p in pockets if p["verdict"].decision == "EXIT"]
    hidden = joint["worst_usd"] - alone["worst_usd"]
    top = shared[0] if shared else None
    headline = (f"{len(exits)} of {len(pockets)} pockets should EXIT" if exits
                else f"All {len(pockets)} pockets can STAY")
    st.markdown(f'<div class="bk-hero"><h2>{headline}</h2><p>Book of {_usd(total)} · '
                f'{len(pockets)} pockets · horizon {horizon} days</p></div>', unsafe_allow_html=True)
    kpis = [
        ("Expected loss", _usd(joint["expected_usd"]), f"{joint['expected_usd'] / total:.2%} of the book"),
        ("Worst 5% of outcomes", _usd(joint["worst_usd"]), f"{joint['worst_usd'] / total:.2%} of the book"),
        ("Hidden by shared dependencies", f"+{_usd(max(0.0, hidden))}",
         "added to the worst 5% vs. pockets judged one by one"),
        ("Most shared dependency", top["name"] if top else "none",
         f"{len(top['pockets'])} of {len(pockets)} pockets rely on it" if top else ""),
    ]
    st.markdown('<div class="bk-kpis">' + "".join(
        f'<div class="bk-kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>'
        for l, v, s in kpis) + "</div>", unsafe_allow_html=True)

    # --- Pocket cards ----------------------------------------------------------
    st.subheader("The pockets")
    cards = []
    for p in sorted(pockets, key=lambda p: (p["verdict"].decision != "EXIT", -p["pos"].size_usd)):
        v, pos, late = p["verdict"], p["pos"], p["late"] or {}
        c = CRITICAL if v.decision == "EXIT" else GOOD
        pill = "✕ EXIT" if v.decision == "EXIT" else "✓ STAY"
        third = ("Out today", f"{late['withdrawable_now']:.0%}") if "withdrawable_now" in late \
            else ("Leaving late", f"{late.get('cost', 0):.2%}")
        cards.append(
            f'<div class="bk-card" style="--c:{c}"><div class="top"><span class="name">{p["label"]}</span>'
            f'<span class="bk-pill">{pill}</span></div>'
            f'<div class="meta">{KIND_LABEL.get(pos.kind, pos.kind)} · {CHAINS.get(pos.chain_id, pos.chain_id)} · '
            f'{_usd(pos.size_usd)} ({pos.size_usd / total:.0%} of book)</div>'
            f'<div class="bk-bar"><div style="width:{pos.size_usd / total:.0%}"></div></div>'
            f'<div class="bk-grid"><div><div class="l">Expected loss</div><div class="v">{v.expected_loss:.2%}</div></div>'
            f'<div><div class="l">Cost to leave</div><div class="v">{v.exit_cost:.2%}</div></div>'
            f'<div><div class="l">{third[0]}</div><div class="v">{third[1]}</div></div></div>'
            f'<div class="bk-why">{_short_reason(p)}</div></div>')
    st.markdown('<div class="bk-cards">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    # --- Where the pockets meet ------------------------------------------------
    st.subheader("Where the pockets meet")
    if not shared:
        st.info("These pockets share no dependency: a failure hits one pocket at a time.")
    else:
        sev = st.select_slider("If a shared dependency loses", [0.05, 0.20, 0.50, 1.00], value=0.50,
                               format_func=lambda s: f"{s:.0%} of its value")
        losses = {d["node_id"]: book.book_stress(pockets, d["node_id"], sev) for d in shared}
        book_usd = {d["node_id"]: sum(l * p["pos"].size_usd for l, p in zip(losses[d["node_id"]], pockets))
                    for d in shared}
        shown = sorted(shared, key=lambda d: -book_usd[d["node_id"]])[:10]
        heat_tab, net_tab = st.tabs(["Heatmap: who loses what", "Network: who relies on what"])
        with heat_tab:
            st.caption(f"Share of each pocket lost if the dependency loses {sev:.0%} (stress engine). "
                       "Darker = worse; blank = the pocket does not rely on it. Right: what the whole "
                       "book loses. Hover a cell for USD.")
            labels = [p["label"] for p in pockets]
            names = {d["node_id"]: f"{d['name']} · {len(d['pockets'])} pockets" for d in shown}
            order = [names[d["node_id"]] for d in shown]
            cells = [{"Dependency": names[d["node_id"]], "Pocket": p["label"], "loss": l,
                      "label": f"{l:.0%}" if l >= 0.005 else "<1%", "usd": _usd(l * p["pos"].size_usd)}
                     for d in shown for k, (p, l) in enumerate(zip(pockets, losses[d["node_id"]]))
                     if k in d["pockets"]]
            df = pd.DataFrame(cells)
            y = alt.Y("Dependency:N", sort=order, title=None, axis=alt.Axis(labelLimit=260))
            base_ch = alt.Chart(df).encode(
                x=alt.X("Pocket:N", sort=labels, scale=alt.Scale(domain=labels), title=None,
                        axis=alt.Axis(orient="top", labelAngle=-30, labelLimit=170, labelOverlap=False)),
                y=y)
            heat = base_ch.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
                color=alt.Color("loss:Q", scale=alt.Scale(domain=[0, 1], range=SEQ),
                                legend=alt.Legend(title="Pocket loses", format="%", orient="bottom")),
                tooltip=[alt.Tooltip("Dependency:N"), alt.Tooltip("Pocket:N"),
                         alt.Tooltip("loss:Q", title="Pocket loses", format=".1%"),
                         alt.Tooltip("usd:N", title="In USD")])
            text = base_ch.mark_text(fontSize=12, fontWeight=600).encode(
                text="label:N",
                color=alt.condition(alt.datum.loss > 0.45, alt.value("white"), alt.value("#0b0b0b")))
            totals = pd.DataFrame([{"Dependency": names[d["node_id"]], "usd": book_usd[d["node_id"]],
                                    "label": _usd(book_usd[d["node_id"]])} for d in shown])
            tot = alt.Chart(totals).encode(y=alt.Y("Dependency:N", sort=order, axis=None),
                                           x=alt.X("usd:Q", title="Book loses (USD)",
                                                   scale=alt.Scale(domain=[0, 1.6 * max(totals["usd"].max(), 1)]),
                                                   axis=alt.Axis(format="~s", tickCount=3, grid=False)))
            tot = tot.mark_bar(color=BAR, cornerRadiusEnd=4, height=16).encode(
                tooltip=[alt.Tooltip("Dependency:N"), alt.Tooltip("label:N", title="Book loses")]) + \
                tot.mark_text(align="left", dx=4, fontSize=11, color="#52514e").encode(text="label:N")
            h = 38 * len(shown)
            st.altair_chart(alt.hconcat((heat + text).properties(height=h, width=82 * len(pockets)),
                                        tot.properties(height=h, width=190), spacing=14)
                            .configure_view(stroke=None), width="content")
        with net_tab:
            st.caption("Left: your pockets. Right: what several of them rely on. Thicker line = the "
                       f"pocket loses more when that dependency loses {sev:.0%}.")
            dot = ['digraph B { rankdir=LR; nodesep=0.18; ranksep=2.2; bgcolor="transparent"; splines=true;',
                   'node [shape=box, style="rounded,filled", fontname=Helvetica, fontsize=12, penwidth=0, margin="0.18,0.08"];',
                   'edge [arrowhead=none];']
            for k, p in enumerate(pockets):
                ok = p["verdict"].decision == "STAY"
                dot.append(f'"p{k}" [label="{"✓ STAY" if ok else "✕ EXIT"}  {p["label"]}", '
                           f'fillcolor="{"#d9f2d9" if ok else "#f6d5d5"}"];')
            for d in shown:
                dot.append(f'"{d["node_id"]}" [label="{d["name"]}\\n{d["type"]}", '
                           f'fillcolor="{TYPE_COLORS.get(d["type"], "#dddddd")}"];')
                for k in d["pockets"]:
                    l = losses[d["node_id"]][k]
                    dot.append(f'"p{k}" -> "{d["node_id"]}" [penwidth={0.5 + 7 * l:.1f}, '
                               f'color="{"#2a78d6" if l >= 0.2 else "#9ec5f4"}", tooltip="{l:.0%}"];')
            dot.append("}")
            st.graphviz_chart("\n".join(dot), width="stretch")

    # --- Book stress test ------------------------------------------------------
    st.subheader("Book stress test: one failure, every pocket")
    all_deps = {f"{d['name']} · {len(d['pockets'])} pockets": d["node_id"] for d in shared}
    for p in pockets:
        for n in p["graph"].nodes:
            if n.id != p["graph"].position_id and n.type != "position":
                all_deps.setdefault(f"{n.name} · 1 pocket", n.id)
    s1, s2 = st.columns([3, 2])
    pick = s1.selectbox("Dependency that fails", list(all_deps))
    hit = s2.slider("It loses (% of its value)", 5, 100, 50, step=5, key="book_hit")
    node_id = all_deps[pick]
    per = book.book_stress(pockets, node_id, hit / 100)
    usd = [l * p["pos"].size_usd for l, p in zip(per, pockets)]
    lost = sum(usd)
    brief = total * book.BRIEF_POCKET_SHARE * book.BRIEF_UNWIND
    m = st.columns(3)
    m[0].metric(f"Book loses ({lost / total:.1%} of it)", _usd(lost))
    m[1].metric("Pockets hit", f"{sum(1 for x in per if x > 0)} of {len(pockets)}")
    m[2].metric("vs. the brief's reference case", f"{lost / brief:.1f}×" if brief else "-",
                help="Brief: 10 pockets of 10%, one affected, unwinding it costs 11% = "
                     f"{book.BRIEF_POCKET_SHARE * book.BRIEF_UNWIND:.1%} of the book ({_usd(brief)}).")
    bars = pd.DataFrame({"Pocket": [p["label"] for p in pockets], "usd": usd,
                         "pct": per, "label": [f"{_usd(u)} ({l:.0%})" if u > 0 else "not exposed" for u, l in zip(usd, per)]})
    bch = alt.Chart(bars).encode(
        y=alt.Y("Pocket:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
        x=alt.X("usd:Q", title="Loss (USD)", axis=alt.Axis(format="~s", tickCount=5, grid=True)))
    chart = bch.mark_bar(color=BAR, cornerRadiusEnd=4, height=18).encode(
        tooltip=[alt.Tooltip("Pocket:N"), alt.Tooltip("usd:Q", title="Loss (USD)", format=",.0f"),
                 alt.Tooltip("pct:Q", title="Share of the pocket", format=".1%")]) + \
        bch.mark_text(align="left", dx=6, fontSize=11, color="#52514e").encode(text="label:N")
    st.altair_chart(chart.properties(height=40 * len(pockets) + 30), width="stretch")

    # --- Action plan -------------------------------------------------------------
    st.subheader("Action plan")
    st.dataframe(pd.DataFrame([{
        "Pocket": p["label"], "Verdict": ("✕ EXIT" if p["verdict"].decision == "EXIT" else "✓ STAY"),
        "What to do": _action(p),
        "Expected loss (USD)": f"{p['risk'].expected_loss * p['pos'].size_usd:,.0f}",
        "Cost to leave (USD)": f"{(p['exit_cost'] + p['forgone']) * p['pos'].size_usd:,.0f}",
        "Why": p["verdict"].reason} for p in pockets]), width="stretch", hide_index=True)
    st.caption("Expected loss and worst 5% come from one Monte Carlo over the whole book: an incident "
               "on a shared dependency is drawn once and hits every pocket that relies on it. "
               "'Hidden by shared dependencies' = that worst 5% minus the one obtained when each "
               "pocket draws its incidents on its own.")
