"""When to exit a lending position before it gets stuck: an optimal-stopping
rule (Snell envelope), solved in closed form.

A lender earns the yield r while staying. Exiting costs C (exit_cost.py). If
the market's utilization reaches 100%, withdrawals freeze and the lender is
trapped through the crisis, losing the haircut H instead of C. Freezes arrive
with a hazard that explodes as utilization u nears 1:

    h(u) = KAPPA / (1 - u)^GAMMA        (per year)

The value of the position is the Snell envelope of "exit now" vs "stay one
more step". Because h(u) only grows with u, the problem is monotone and the
one-step look-ahead rule is optimal (Chow, Robbins & Siegmund, "Great
Expectations: the theory of optimal stopping", 1971): exit as soon as staying
one more step costs more than it pays,

    h(u) * (H - C)  >  r        <=>        u  >  u* = 1 - (KAPPA (H - C) / r)^(1 / GAMMA)

H comes from the stress engine (the position's loss when its main collateral
falls 50%); r from the protocol's APY; KAPPA and GAMMA are JUDGEMENT (no public
history of Morpho/Kamino freezes to fit them on yet).
"""

import networkx as nx

from src.risk.model import path_exposure, to_networkx
from src.risk.stress import loop_gains, position_loss
from src.schemas import DependencyGraph

GAMMA = 2.0     # JUDGEMENT: how fast the hazard explodes near 100% utilization
# JUDGEMENT anchor: lending rate curves (Morpho's adaptive IRM, Kamino's kinked
# curve) keep utilization near 90% on purpose; a market sitting at that target
# is taken to freeze once every five years. KAPPA follows from that anchor.
TARGET_UTILIZATION, HAZARD_AT_TARGET = 0.90, 0.2
KAPPA = HAZARD_AT_TARGET * (1 - TARGET_UTILIZATION) ** GAMMA
CRISIS_DROP = 0.5   # JUDGEMENT: collateral crash that a trapped lender sits through
DEFAULT_YIELD = 0.05


def position_utilization(g: DependencyGraph) -> float | None:
    """Utilization of the lending markets the position is in, weighted by how
    much of the position each one carries."""
    G = to_networkx(g)
    pairs = [(path_exposure(G, g.position_id, n.id), n.meta.get("utilization"))
             for n in g.nodes if n.type == "lending" and n.meta.get("utilization") is not None
             and n.meta.get("role") != "contagion" and nx.has_path(G, g.position_id, n.id)]
    total = sum(w for w, _ in pairs)
    return sum(w * u for w, u in pairs) / total if total else None


def position_yield(g: DependencyGraph) -> float:
    for n in [g.node(g.position_id)] + [n for n in g.nodes if n.type == "vault"]:
        r = n.meta.get("net_apy") or n.meta.get("supply_apy")
        if r:
            return float(r)
    return DEFAULT_YIELD


def trapped_haircut(g: DependencyGraph) -> tuple[float, str]:
    """Loss of the position if it sits through a CRISIS_DROP of its worst collateral."""
    gains = loop_gains(g)
    collaterals = {e.target for e in g.edges if e.kind == "secured_by"}
    worst = max(((position_loss(g, c, CRISIS_DROP, gains), c) for c in collaterals),
                default=(0.0, None))
    name = g.node(worst[1]).name if worst[1] else "none"
    return worst[0], name


def exit_rule(g: DependencyGraph, exit_cost: float) -> dict | None:
    """Current utilization, the exit threshold u*, and whether it is crossed.
    None for positions without lending markets (no freeze risk to time)."""
    u = position_utilization(g)
    if u is None:
        return None
    r = position_yield(g)
    H, collateral = trapped_haircut(g)
    hazard = KAPPA / max(1e-6, 1 - u) ** GAMMA
    if H <= exit_cost or r <= 0:
        u_star = 1.0  # being trapped costs no more than leaving: never worth exiting early
    else:
        u_star = max(0.0, 1 - (KAPPA * (H - exit_cost) / r) ** (1 / GAMMA))
    return {"utilization": u, "u_star": u_star, "triggered": u >= u_star, "yield": r,
            "haircut": H, "hazard_per_year": hazard,
            "rationale": (f"Exit when utilization > u* = 1 - (KAPPA (H - C) / r)^(1/GAMMA) = "
                          f"{u_star:.1%}: yield r = {r:.2%}, haircut if trapped H = {H:.1%} "
                          f"(stress engine: {collateral} -{CRISIS_DROP:.0%}), exit cost C = "
                          f"{exit_cost:.2%}, GAMMA = {GAMMA}, KAPPA set so a market at the {TARGET_UTILIZATION:.0%} "
                          f"target utilization freezes {HAZARD_AT_TARGET}/year (JUDGEMENT). Now "
                          f"{u:.1%}: freeze hazard {hazard:.2f}/year.")}
