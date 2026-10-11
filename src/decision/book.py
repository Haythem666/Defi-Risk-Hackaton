"""The whole book: several pockets judged together.

Each pocket gets the single-pocket pipeline (graph, scenarios, late exit,
verdict). What the book adds is what the pockets share: node ids are the same
across graphs (chain:ethereum, asset:USDC, protocol:morpho-blue...), so a
dependency several pockets rely on is one failure for all of them, not one per
pocket. The book's Monte Carlo draws each incident once and hits every pocket
that depends on it; drawing them per pocket instead shows what pretending the
pockets are independent would hide.
"""

import numpy as np

from src.decision.exit_cost import exit_cost, late_exit
from src.decision.rule import decide, with_late_exit
from src.decision.snell import exit_rule, position_yield
from src.graph.build import build_graph
from src.risk import stress
from src.risk.model import build_scenarios, simulate
from src.schemas import DependencyGraph, Position

# Brief reference: 10 pockets of 10%, one affected, unwinding it costs 11%.
BRIEF_POCKET_SHARE, BRIEF_UNWIND = 0.10, 0.11
SKIP_TYPES = {"position"}


def evaluate(pos: Position, graph: DependencyGraph | None = None) -> dict:
    """The single-pocket decision, as the app's pocket view computes it."""
    g = graph or build_graph(pos)
    late = late_exit(pos, g)
    scenarios = with_late_exit(build_scenarios(g, pos.horizon_days), late["cost"] if late else 0.0)
    risk = simulate(scenarios)
    cost, cost_source = exit_cost(pos, g)
    rule = exit_rule(g, cost)
    apy = position_yield(g)
    forgone = apy * pos.horizon_days / 365
    verdict = decide(risk, cost, forgone, rule)
    return {"pos": pos, "graph": g, "scenarios": scenarios, "risk": risk, "exit_cost": cost,
            "cost_source": cost_source, "late": late, "rule": rule, "apy": apy,
            "forgone": forgone, "verdict": verdict}


def shared_dependencies(pockets: list[dict], min_pockets: int = 2) -> list[dict]:
    """Dependencies that at least `min_pockets` pockets rely on, most shared first."""
    seen: dict[str, dict] = {}
    for k, p in enumerate(pockets):
        g = p["graph"]
        for n in g.nodes:
            if n.type in SKIP_TYPES or n.id == g.position_id:
                continue
            d = seen.setdefault(n.id, {"node_id": n.id, "name": n.name, "type": n.type, "pockets": []})
            if k not in d["pockets"]:
                d["pockets"].append(k)
    out = [d for d in seen.values() if len(d["pockets"]) >= min_pockets]
    return sorted(out, key=lambda d: (-len(d["pockets"]), d["name"]))


def book_stress(pockets: list[dict], node_id: str, severity: float) -> list[float]:
    """Loss of each pocket (fraction of it) when `node_id` loses `severity`."""
    return [stress.position_loss(p["graph"], node_id, severity)
            if any(n.id == node_id for n in p["graph"].nodes) else 0.0 for p in pockets]


def simulate_book(pockets: list[dict], n_runs: int = 20_000, tail: float = 0.05,
                  seed: int = 0, shared: bool = True) -> dict:
    """Book loss in USD. shared=True: an incident on a node is one draw for
    every pocket that has it. shared=False: each pocket draws its own (what a
    pocket-by-pocket view implicitly assumes)."""
    keys, probs = {}, []
    for k, p in enumerate(pockets):
        for s in p["scenarios"]:
            key = (s.node_id, s.incident) if shared else (k, s.node_id, s.incident)
            if key not in keys:
                keys[key] = len(probs)
                probs.append(s.probability)
            else:
                probs[keys[key]] = max(probs[keys[key]], s.probability)
    if not probs:
        return {"expected_usd": 0.0, "worst_usd": 0.0}
    rng = np.random.default_rng(seed)
    hits = rng.random((n_runs, len(probs))) < np.array(probs)
    book = np.zeros(n_runs)
    for k, p in enumerate(pockets):
        survive = np.ones(n_runs)
        for s in p["scenarios"]:
            key = (s.node_id, s.incident) if shared else (k, s.node_id, s.incident)
            survive *= np.where(hits[:, keys[key]], 1 - s.loss_if_hit, 1.0)
        book += p["pos"].size_usd * (1 - survive)
    m = max(1, int(n_runs * tail))
    return {"expected_usd": float(book.mean()), "worst_usd": float(np.sort(book)[-m:].mean())}
