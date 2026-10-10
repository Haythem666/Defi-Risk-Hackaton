"""Stress engine: what each failure in the graph costs the position.

The graph is a matrix W: W[i][j] = share of node i's value that a loss at node
j passes on (the exposure on the edge i -> j, "i depends on j"). A shock is a
vector s (s[j] = fraction node j loses). Losses move up the edges round after
round until nothing changes:

    L = s;  repeat  L_i = max(s_i, min(1, sum_j f_ij(L_j)))  until stable

This is DebtRank's capped propagation (Battiston et al. 2012) computed as the
fixed point Eisenberg & Noe (2001) prove exists: each step is monotone and
bounded by 1, so it converges, loops included, and no loss exceeds 100%.

Edges come in two kinds. A *value* edge carries a distinct slice of the node's
value (a vault's 30% in a market, a reserve lent against a collateral): slices
add up. A *common* edge is a dependency of the node's whole value (the chain it
runs on, the protocol's code, its oracle, its issuer): one failure reaching a
node through several such edges is still one failure, so they combine by max:

    L_i = min(1, max( sum over value edges f_ij(L_j),  max over common edges f_ij(L_j) ))

Most edges pass losses on linearly: f_ij(L) = W[i][j] * L. Two mechanisms do not:

1. A lender and its collateral (edge "secured_by"). Borrowers sit, at worst, at
   the market's max loan-to-value (LLTV): a price drop d smaller than the buffer
   1 - LLTV leaves every loan covered. Above it, the lender is left with the
   collateral, worth (1 - d) and sold at a price impact `impact` (1 if no DEX
   trades it), against a debt of LLTV:
       shortfall = max(0, 1 - (1 - d)(1 - impact) / LLTV)     if d > 1 - LLTV
   and the market loses exposure (share lent out) x shortfall.

2. The liquidation spiral of a collateral. A drop of SPIRAL_SHOCK forces sales
   (Morpho marketCollateralAtRisk, plus other lenders holding it) whose price
   impact we quoted on DEXes. Loop gain g = extra drop / initial drop. g < 1: the
   spiral damps out, total drop = d / (1 - g) (geometric series). g >= 1: it
   feeds itself until the forced sales run out: drop = 1 - (1 - d)(1 - impact).
   Liquidators only sell while it pays: if the impact exceeds the liquidation
   bonus (or no DEX trades the token) they stop, there is no spiral, and the
   loss arrives as bad debt instead, through the shortfall above ("stalled").

Running a shock of each size on each node fills the impact matrix
T[i][j] = loss of i when j is hit; the position's row of T is the answer to
"what does each failure cost me". For the spectral view, the linear part of W
plus the spiral gains on the diagonal has spectral radius rho = max loop gain on
a graph whose only loops are spirals: rho >= 1 means a self-feeding cascade.
"""

import numpy as np

from src.schemas import DependencyGraph, Edge, Node

SEVERITIES = (0.05, 0.20, 0.50, 1.00)
SPIRAL_SHOCK = 0.05     # the drop at which forced sales were measured (graph/collateral.py SHOCK)
DEFAULT_LLTV = 0.80     # when the market does not publish one (Aave pools: per-asset, not fetched)
MAX_ROUNDS = 200
# Edges that carry a distinct slice of the source's value (they add up).
VALUE_EDGES = {"allocates_to", "supplied_to", "deposited_in", "secured_by", "hedges_on",
               "holds_position_in", "holds", "redeems_into", "share_of"}


def _index(g: DependencyGraph) -> tuple[dict[str, Node], dict[str, list[Edge]]]:
    nodes = {n.id: n for n in g.nodes}
    deps: dict[str, list[Edge]] = {n.id: [] for n in g.nodes}
    for e in g.edges:
        deps[e.source].append(e)  # source depends on target
    return nodes, deps


def _exit_impact(nodes: dict[str, Node], deps: dict[str, list[Edge]], lend: Node) -> float:
    """Price impact a lender's liquidators would face selling the collateral:
    1 when no DEX trades it, else the quoted impact (0 if never quoted)."""
    for e in deps[lend.id]:
        if e.kind == "liquidated_via" and nodes[e.target].meta.get("has_market") is False:
            return 1.0
    return float(lend.meta.get("liquidation_price_impact") or 0.0)


def _lltv(lend: Node, collateral_id: str) -> float:
    by_asset = lend.meta.get("lltv_by_asset") or {}
    return float(by_asset.get(collateral_id) or lend.meta.get("lltv") or DEFAULT_LLTV)


def shortfall(drop: float, lltv: float, impact: float) -> float:
    """Share of a loan lost when its collateral falls by `drop` (see module doc)."""
    if drop <= 1 - lltv:
        return 0.0
    return min(1.0, max(0.0, 1 - (1 - drop) * (1 - impact) / lltv))


def loop_gains(g: DependencyGraph) -> dict[str, dict]:
    """Liquidation spiral of each collateral that has measured forced sales."""
    nodes, deps = _index(g)
    out = {}
    for a in (n for n in g.nodes if n.type == "asset"):
        lenders = [nodes[e.source] for e in g.edges if e.kind == "secured_by" and e.target == a.id]
        measured = [l for l in lenders if l.meta.get("liquidated_at_shock_usd") is not None]
        if not measured:
            continue
        forced = sum(l.meta.get("liquidated_at_shock_usd") or 0 for l in measured)
        no_market = any(_exit_impact(nodes, deps, l) >= 1.0 for l in measured)
        impact = 1.0 if no_market else max(float(l.meta.get("liquidation_price_impact") or 0)
                                           for l in measured)
        others = sum(nodes[e.target].meta.get("collateral_usd") or 0 for e in deps[a.id]
                     if e.kind == "also_collateral_in")
        if forced > 0 and impact < 1:  # other lenders' forced sales hit the same DEX depth
            impact = min(1.0, impact * (forced + SPIRAL_SHOCK * others) / forced)
        if forced <= 0 and not no_market:
            continue
        bonus = min(float(l.meta.get("liquidation_bonus") or 0.05) for l in measured)
        stalled = no_market or impact > bonus  # liquidators would lose money: they stop
        gain = None if stalled else impact / SPIRAL_SHOCK
        out[a.id] = {"asset": a.name, "gain": gain, "impact": impact, "bonus": bonus,
                     "forced_usd": forced + SPIRAL_SHOCK * others,
                     "phase": "stalled" if stalled else ("supercritical" if gain >= 1 else "damped"),
                     "rationale": (f"a {SPIRAL_SHOCK:.0%} drop forces {forced:,.0f} USD of sales in "
                                   f"the markets drawn (+{SPIRAL_SHOCK:.0%} of {others:,.0f} USD held by "
                                   f"other lenders); selling it moves the price {impact:.1%} "
                                   f"(DEX/Pendle quotes) vs a {bonus:.1%} liquidation bonus: "
                                   + ("liquidators stop, losses arrive as bad debt" if stalled else
                                      f"gain = {impact:.1%} / {SPIRAL_SHOCK:.0%}"))}
    return out


def _amplify(drop: float, spiral: dict | None) -> float:
    if not spiral or spiral["gain"] is None or drop < SPIRAL_SHOCK:
        return drop
    bound = 1 - (1 - drop) * (1 - spiral["impact"])  # every forced sale executed
    if spiral["gain"] >= 1:
        return bound
    return min(bound, drop / (1 - spiral["gain"]))


def propagate(g: DependencyGraph, shocks: dict[str, float],
              gains: dict[str, dict] | None = None) -> dict[str, float]:
    """Loss of every node (fraction of its value) after `shocks` spread."""
    nodes, deps = _index(g)
    gains = loop_gains(g) if gains is None else gains
    loss = {i: 0.0 for i in nodes}
    loss.update({i: min(1.0, s) for i, s in shocks.items() if i in loss})
    for _ in range(MAX_ROUNDS):
        changed = False
        for i, n in nodes.items():
            value, common = 0.0, 0.0
            for e in deps[i]:
                lj = loss[e.target]
                if lj <= 0:
                    continue
                if e.kind == "secured_by":
                    f = e.exposure * shortfall(lj, _lltv(n, e.target), _exit_impact(nodes, deps, n))
                else:
                    f = e.exposure * lj
                if e.kind in VALUE_EDGES:
                    value += f
                else:
                    common = max(common, f)
            new = max(shocks.get(i, 0.0), min(1.0, max(value, common)))
            if n.type == "asset":
                new = max(new, _amplify(new, gains.get(i)))
            if new > loss[i] + 1e-12:
                loss[i], changed = new, True
        if not changed:
            break
    return loss


def position_loss(g: DependencyGraph, node_id: str, severity: float,
                  gains: dict[str, dict] | None = None) -> float:
    return propagate(g, {node_id: severity}, gains)[g.position_id]


def stress_table(g: DependencyGraph, severities=SEVERITIES) -> list[dict]:
    """Position loss for each node hit at each severity, worst first."""
    gains = loop_gains(g)
    rows = []
    for n in g.nodes:
        if n.id == g.position_id:
            continue
        losses = {s: position_loss(g, n.id, s, gains) for s in severities}
        if max(losses.values()) <= 0:
            continue
        rows.append({"node_id": n.id, "name": n.name, "type": n.type, "losses": losses})
    rows.sort(key=lambda r: -r["losses"][severities[-2] if len(severities) > 1 else severities[0]])
    return rows


def impact_matrix(g: DependencyGraph, severity: float = 1.0) -> tuple[list[str], np.ndarray]:
    """T[i][j] = loss of node i when node j alone is hit at `severity`."""
    ids = [n.id for n in g.nodes]
    gains = loop_gains(g)
    T = np.zeros((len(ids), len(ids)))
    for j, nid in enumerate(ids):
        loss = propagate(g, {nid: severity}, gains)
        T[:, j] = [loss[i] for i in ids]
    return ids, T


def spectral(g: DependencyGraph) -> dict:
    """Linear part of W, with the spiral gains as self-loops on the diagonal.
    rho = its spectral radius; the dominant eigenvector shows where a cascade
    concentrates. On our graphs the only loops are spirals, so rho = the
    largest loop gain: >= 1 means a self-feeding cascade (supercritical)."""
    ids = [n.id for n in g.nodes]
    pos = {i: k for k, i in enumerate(ids)}
    W = np.zeros((len(ids), len(ids)))
    for e in g.edges:
        W[pos[e.source], pos[e.target]] += e.exposure
    gains = loop_gains(g)
    for aid, sp in gains.items():
        if sp["gain"] is not None:
            W[pos[aid], pos[aid]] = sp["gain"]
    vals, vecs = np.linalg.eig(W.T)  # left eigenvectors of W: where shocks start biggest cascades
    k = int(np.argmax(np.abs(vals)))
    rho = float(abs(vals[k]))
    weight = np.abs(np.real(vecs[:, k]))
    top = [ids[i] for i in np.argsort(-weight)[:3] if weight[i] > 1e-9] if rho > 0 else []
    return {"rho": rho, "phase": "supercritical" if rho >= 1 else ("damped" if rho > 0 else "no loop"),
            "top_sources": top, "gains": gains, "W": W, "ids": ids}
